"""
Pipeline stage (post-save): match a processed receipt to a bank transaction.

After a receipt is saved we attempt to reconcile it with the user's bank
transactions using their stored Plaid access token. A receipt is matched to a
transaction when the **amount** and the **timestamp** (date) line up within a
small tolerance.

The user's Plaid credentials live only in Secrets Manager. Either the user's
own ``client_id``/``secret`` (``plaid/credentials/{userId}``) — which are used
to mint and exchange a token at match time — or a directly-registered access
token (``plaid/access-token/{userId}``). Neither is ever written to DynamoDB;
only the resulting match metadata (transaction id, name, amount, date) is
persisted on the receipt.

This stage is best-effort: a missing token, a Plaid outage, or simply finding
no candidate transaction must never fail the pipeline. Every such case is
recorded in ``transactionMatchStatus`` and the receipt is left COMPLETED.
"""

import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["RECEIPTS_TABLE_NAME"])
secrets = boto3.client("secretsmanager")

# Amount tolerance (absolute, in the receipt currency) and the number of days
# on either side of the receipt date we are willing to consider a match.
AMOUNT_TOLERANCE = 0.02
MAX_DAY_DIFF = 3

PLAID_URLS = {
    "sandbox": "https://sandbox.plaid.com",
    "production": "https://production.plaid.com",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _to_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def transaction_amount(txn):
    """Plaid encodes outflows as positive amounts; receipts use positives too."""
    amount = _to_float(txn.get("amount"))
    if amount is None:
        return None
    return abs(amount)


def transaction_date(txn):
    return txn.get("date")


def _parse_date(value):
    if not value:
        return None
    # Plaid dates are YYYY-MM-DD; datetimes may carry a time/offset suffix.
    text = str(value)[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def date_diff_days(date_a, date_b):
    parsed_a = _parse_date(date_a)
    parsed_b = _parse_date(date_b)
    if parsed_a is None or parsed_b is None:
        return None
    return abs((parsed_a - parsed_b).days)


def find_matching_transaction(
    transactions,
    target_amount,
    target_date,
    amount_tolerance=AMOUNT_TOLERANCE,
    max_day_diff=MAX_DAY_DIFF,
):
    """Return the best transaction matching the receipt amount and date, or None.

    Candidates must fall within ``amount_tolerance`` of the receipt total and
    within ``max_day_diff`` days of the receipt date. The closest amount wins,
    with the smallest date gap breaking ties.
    """
    if target_amount is None:
        return None

    best = None
    best_score = None
    for txn in transactions or []:
        amount = transaction_amount(txn)
        if amount is None:
            continue
        amount_gap = abs(amount - target_amount)
        if amount_gap > amount_tolerance:
            continue

        day_gap = date_diff_days(transaction_date(txn), target_date)
        if day_gap is None or day_gap > max_day_diff:
            continue

        score = (amount_gap, day_gap)
        if best_score is None or score < best_score:
            best = txn
            best_score = score

    return best


def _get_access_token(user_id):
    try:
        secret = secrets.get_secret_value(SecretId=f"plaid/access-token/{user_id}")
    except secrets.exceptions.ResourceNotFoundException:
        return None
    data = json.loads(secret["SecretString"])
    return data.get("accessToken")


def _get_user_credentials(user_id):
    """Return the user's own Plaid ``client_id``/``secret`` (or None).

    These are the per-user credentials registered via ``POST /bank/config`` and
    stored at ``plaid/credentials/{userId}``. They are used to authenticate to
    Plaid and derive an access token at match time.
    """
    try:
        secret = secrets.get_secret_value(SecretId=f"plaid/credentials/{user_id}")
    except secrets.exceptions.ResourceNotFoundException:
        return None
    data = json.loads(secret["SecretString"])
    if data.get("clientId") and data.get("secret"):
        return data
    return None


def _get_plaid_creds():
    secret = secrets.get_secret_value(SecretId="plaid/credentials")
    return json.loads(secret["SecretString"])


def _plaid_post(base_url, path, payload):
    req = urllib.request.Request(
        f"{base_url}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _create_access_token(creds):
    """Authenticate with the user's credentials to derive a Plaid access token.

    In the sandbox flow we mint a public token for a test institution and
    immediately exchange it for an access token, mirroring what a real Plaid
    Link connection would yield.
    """
    base_url = PLAID_URLS.get(creds.get("env"), PLAID_URLS["sandbox"])

    # ins_109508 is Plaid's default sandbox test institution ("First Platypus
    # Bank"); callers may override it via the stored credentials.
    public = _plaid_post(base_url, "/sandbox/public_token/create", {
        "client_id": creds["clientId"],
        "secret": creds["secret"],
        "institution_id": creds.get("institutionId", "ins_109508"),
        "initial_products": ["transactions"],
    })
    public_token = public.get("public_token")
    if not public_token:
        return None

    exchanged = _plaid_post(base_url, "/item/public_token/exchange", {
        "client_id": creds["clientId"],
        "secret": creds["secret"],
        "public_token": public_token,
    })
    return exchanged.get("access_token")


def _fetch_transactions(creds, access_token, start_date, end_date):
    base_url = PLAID_URLS.get(creds.get("env"), PLAID_URLS["sandbox"])
    payload = json.dumps({
        "client_id": creds["clientId"],
        "secret": creds["secret"],
        "access_token": access_token,
        "start_date": start_date,
        "end_date": end_date,
        "options": {"count": 250},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/transactions/get",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read())
    return result.get("transactions", [])


def _load_receipt(user_id, receipt_id):
    result = table.get_item(Key={"userId": user_id, "receiptId": receipt_id})
    return result.get("Item")


def _record_match(user_id, receipt_id, status, transaction=None):
    fields = {
        "transactionMatchStatus": status,
        "transactionMatchedAt": now_iso(),
    }
    if transaction is not None:
        fields["matchedTransactionId"] = transaction.get("transaction_id")
        fields["matchedTransactionName"] = (
            transaction.get("merchant_name") or transaction.get("name")
        )
        amount = transaction_amount(transaction)
        fields["matchedTransactionAmount"] = str(amount) if amount is not None else None
        fields["matchedTransactionDate"] = transaction_date(transaction)

    fields = {k: v for k, v in fields.items() if v is not None}

    names = {}
    values = {}
    set_parts = []
    for i, (k, v) in enumerate(fields.items()):
        names[f"#m{i}"] = k
        values[f":m{i}"] = v
        set_parts.append(f"#m{i} = :m{i}")

    table.update_item(
        Key={"userId": user_id, "receiptId": receipt_id},
        UpdateExpression="SET " + ", ".join(set_parts),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def handler(event, context):
    user_id = event["userId"]
    receipt_id = event["receiptId"]

    status = "NO_MATCH"
    matched = None
    try:
        user_creds = _get_user_credentials(user_id)
        access_token = None

        if user_creds:
            # Preferred flow: authenticate with the user's own credentials and
            # derive an access token to query their transactions.
            creds = user_creds
            access_token = _create_access_token(user_creds)
        else:
            # Fallback: a directly-registered access token plus shared creds.
            access_token = _get_access_token(user_id)
            creds = _get_plaid_creds() if access_token else None

        if not access_token:
            print(f"[Match] No Plaid connection for user {user_id}; skipping match.")
            _record_match(user_id, receipt_id, "NO_BANK_CONNECTION")
            event["transactionMatchStatus"] = "NO_BANK_CONNECTION"
            return event

        receipt = _load_receipt(user_id, receipt_id) or {}
        target_amount = _to_float(receipt.get("totalAmount"))
        receipt_date = receipt.get("receiptDate")

        if target_amount is None or not receipt_date:
            print(
                f"[Match] Receipt {receipt_id} missing amount/date; cannot match."
            )
            _record_match(user_id, receipt_id, "INSUFFICIENT_DATA")
            event["transactionMatchStatus"] = "INSUFFICIENT_DATA"
            return event

        center = _parse_date(receipt_date)
        start_date = (center - timedelta(days=MAX_DAY_DIFF)).strftime("%Y-%m-%d")
        end_date = (center + timedelta(days=MAX_DAY_DIFF)).strftime("%Y-%m-%d")

        transactions = _fetch_transactions(
            creds, access_token, start_date, end_date
        )

        matched = find_matching_transaction(
            transactions, target_amount, receipt_date
        )
        status = "MATCHED" if matched else "NO_MATCH"
        _record_match(user_id, receipt_id, status, matched)

    except Exception as exc:  # best-effort: never fail the pipeline here
        print(f"[Match] Error matching receipt {receipt_id}: {exc}")
        status = "ERROR"
        try:
            _record_match(user_id, receipt_id, status)
        except Exception as record_exc:
            print(f"[Match] Could not record match status: {record_exc}")

    print(f"[Match] Receipt {receipt_id} match result: {status}")
    event["transactionMatchStatus"] = status
    return event
