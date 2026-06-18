import os
import json
import boto3
import urllib.request
import urllib.parse

from decimal import Decimal
from difflib import SequenceMatcher
from datetime import timedelta, date
from datetime import datetime, timezone


dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["RECEIPTS_TABLE_NAME"])

s3_client = boto3.client("s3")
textract_client = boto3.client("textract")
bedrock = boto3.client("bedrock-runtime", region_name="eu-central-1")

BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "eu.amazon.nova-lite-v1:0")

MAX_FIELD_LENGTH = 200
MAX_RECEIPT_ITEMS = 50

CATEGORIES = [
    "Groceries",
    "Dining",
    "Entertainment",
    "Transport",
    "Health",
    "Shopping",
    "Utilities",
    "Other",
]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def sanitize_for_dynamodb(value):
    """
    Recursively converts floats to Decimal for DynamoDB compatibility.
    """
    if isinstance(value, float):
        return Decimal(str(value))

    if isinstance(value, dict):
        return {k: sanitize_for_dynamodb(v) for k, v in value.items()}

    if isinstance(value, list):
        return [sanitize_for_dynamodb(item) for item in value]

    return value


def update_status(user_id, receipt_id, status, extra_fields=None):
    """
    Updates the receipt record in DynamoDB using ExpressionAttributeNames
    to avoid reserved-word conflicts.
    """
    update_parts = [
        "#processingStatus = :processingStatus",
        "#updatedAt = :updatedAt",
    ]

    expr_names = {
        "#processingStatus": "processingStatus",
        "#updatedAt": "updatedAt",
    }

    expr_values = {
        ":processingStatus": status,
        ":updatedAt": now_iso(),
    }

    if extra_fields:
        for index, (key, value) in enumerate(extra_fields.items()):
            name_key = f"#field{index}"
            value_key = f":field{index}"

            update_parts.append(f"{name_key} = {value_key}")
            expr_names[name_key] = key
            expr_values[value_key] = sanitize_for_dynamodb(value)

    table.update_item(
        Key={
            "userId": user_id,
            "receiptId": receipt_id,
        },
        UpdateExpression="SET " + ", ".join(update_parts),
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )


def clean_amount_string(value):
    """
    Converts amount-like values into a clean numeric string.
    Examples:
      "CHF 3,20" -> "3.20"
      "€12.50"   -> "12.50"
      4.5        -> "4.5"
    """
    if value is None:
        return None

    cleaned = (
        str(value)
        .replace("CHF", "")
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .replace(",", ".")
        .strip()
    )

    if cleaned == "":
        return None

    try:
        amount = float(cleaned)
        if amount < 0:
            return None
    except (ValueError, TypeError):
        return None

    return cleaned


def parse_amount(value):
    cleaned = clean_amount_string(value)
    if cleaned is None:
        return None

    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Textract AnalyzeExpense extraction
# ---------------------------------------------------------------------------

def extract_field_value(field):
    """Extract value text from a Textract expense field."""
    value_detection = field.get("ValueDetection")
    if value_detection:
        return value_detection.get("Text")
    return None


def extract_field_type(field):
    """Extract the type label from a Textract expense field."""
    field_type = field.get("Type")
    if field_type:
        return field_type.get("Text", "").upper()
    return ""


def parse_textract_expense(response):
    """
    Parses Textract AnalyzeExpense response into structured receipt data.

    Extracts:
      - Summary fields: merchant, date, totals, tax, subtotal, currency
      - Line items: name, quantity, price per item
    """
    receipt_data = {
        "merchantName": None,
        "receiptDate": None,
        "receiptTime": None,
        "totalAmount": None,
        "subtotalAmount": None,
        "taxAmount": None,
        "tipAmount": None,
        "currency": None,
        "receiptItems": [],
    }

    expense_documents = response.get("ExpenseDocuments", [])
    if not expense_documents:
        return receipt_data

    doc = expense_documents[0]

    # --- Extract summary fields ---
    summary_fields = doc.get("SummaryFields", [])
    for field in summary_fields:
        field_type = extract_field_type(field)
        value = extract_field_value(field)

        if not value:
            continue

        if field_type in ("VENDOR_NAME", "SUPPLIER_NAME", "NAME"):
            if not receipt_data["merchantName"]:
                receipt_data["merchantName"] = value.strip()[:MAX_FIELD_LENGTH]

        elif field_type in ("INVOICE_RECEIPT_DATE", "ORDER_DATE"):
            receipt_data["receiptDate"] = normalize_date(value)

        elif field_type == "INVOICE_RECEIPT_TIME":
            receipt_data["receiptTime"] = value.strip()

        elif field_type == "TOTAL":
            receipt_data["totalAmount"] = clean_amount_string(value)

        elif field_type == "SUBTOTAL":
            receipt_data["subtotalAmount"] = clean_amount_string(value)

        elif field_type == "TAX":
            receipt_data["taxAmount"] = clean_amount_string(value)

        elif field_type in ("GRATUITY", "TIP"):
            receipt_data["tipAmount"] = clean_amount_string(value)

        elif field_type == "RECEIVER_ADDRESS" and not receipt_data["merchantName"]:
            receipt_data["merchantName"] = value.strip()[:MAX_FIELD_LENGTH]

    # Try to detect currency from amount fields
    for field in summary_fields:
        value = extract_field_value(field)
        if value:
            currency = detect_currency(value)
            if currency:
                receipt_data["currency"] = currency
                break

    # --- Extract line items ---
    line_item_groups = doc.get("LineItemGroups", [])
    for group in line_item_groups:
        for line_item in group.get("LineItems", []):
            item = parse_line_item(line_item)
            if item:
                receipt_data["receiptItems"].append(item)

    # Limit to configured maximum items
    receipt_data["receiptItems"] = receipt_data["receiptItems"][:MAX_RECEIPT_ITEMS]

    return receipt_data


def parse_line_item(line_item):
    """
    Parses a single Textract line item into {name, quantity, price}.
    """
    item_name = None
    item_quantity = None
    item_price = None

    for field in line_item.get("LineItemExpenseFields", []):
        field_type = extract_field_type(field)
        value = extract_field_value(field)

        if not value:
            continue

        if field_type == "ITEM":
            item_name = value.strip()[:MAX_FIELD_LENGTH]
        elif field_type == "QUANTITY":
            item_quantity = value.strip()
        elif field_type in ("PRICE", "UNIT_PRICE"):
            item_price = clean_amount_string(value)
        elif field_type == "EXPENSE_ROW" and not item_name:
            item_name = value.strip()[:MAX_FIELD_LENGTH]

    if item_name is None and item_price is None:
        return None

    return {
        "name": item_name,
        "quantity": item_quantity,
        "price": item_price,
    }


def normalize_date(value):
    """
    Attempts to parse various date formats into YYYY-MM-DD.
    """
    if not value:
        return None

    value = value.strip()

    date_formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d.%m.%Y",
        "%d-%m-%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ]

    for fmt in date_formats:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return value


def detect_currency(text):
    """Detects currency from common symbols in amount text."""
    if not text:
        return None

    text = str(text)

    if "CHF" in text:
        return "CHF"
    if "€" in text:
        return "EUR"
    if "£" in text:
        return "GBP"
    if "$" in text:
        return "USD"

    return None


# ---------------------------------------------------------------------------
# Bedrock categorization
# ---------------------------------------------------------------------------

def categorize_with_bedrock(receipt_data):
    """
    Uses Bedrock to categorize the receipt based on extracted metadata.
    Returns one of the valid CATEGORIES.
    """
    merchant = receipt_data.get("merchantName") or "Unknown"
    items = receipt_data.get("receiptItems") or []

    item_names = [item["name"] for item in items[:10] if item.get("name")]
    items_text = ", ".join(item_names) if item_names else "No items extracted"

    prompt_text = (
        f"Merchant: {merchant}\n"
        f"Items: {items_text}\n"
        f"Total: {receipt_data.get('totalAmount') or 'unknown'}\n\n"
        f"Categorize this receipt into exactly ONE of these categories: "
        f"{', '.join(CATEGORIES)}.\n"
        f"Respond with ONLY the category name, nothing else."
    )

    body = json.dumps({
        "system": [
            {
                "text": (
                    "You are a receipt categorization service. "
                    "You respond with exactly one category name from the given list. "
                    "No explanations, no punctuation, just the category."
                )
            }
        ],
        "messages": [
            {
                "role": "user",
                "content": [{"text": prompt_text}],
            }
        ],
        "inferenceConfig": {
            "max_new_tokens": 20,
        },
    })

    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=body,
        )

        response_body = json.loads(response["body"].read())
        category = (
            response_body["output"]["message"]["content"][0]["text"]
            .strip()
            .title()
        )

        if category in CATEGORIES:
            return category

        # Fuzzy match in case of slight variations
        for valid_category in CATEGORIES:
            if valid_category.lower() in category.lower():
                return valid_category

    except Exception as error:
        print(f"Bedrock categorization failed: {str(error)}")

    return "Other"


# ---------------------------------------------------------------------------
# Textract receipt processing
# ---------------------------------------------------------------------------

def process_receipt_image(bucket, key):
    """
    Processes a receipt image using Textract AnalyzeExpense for structured
    data extraction, then uses Bedrock for categorization.
    """
    textract_response = textract_client.analyze_expense(
        Document={
            "S3Object": {
                "Bucket": bucket,
                "Name": key,
            }
        }
    )

    receipt_data = parse_textract_expense(textract_response)

    # Use Bedrock to categorize the receipt
    category = categorize_with_bedrock(receipt_data)
    receipt_data["category"] = category

    return receipt_data


# ---------------------------------------------------------------------------
# Plaid transaction matching (kept as-is)
# ---------------------------------------------------------------------------

def get_plaid_transactions(user_id, receipt_date):
    secrets_client = boto3.client("secretsmanager")

    try:
        secret = secrets_client.get_secret_value(
            SecretId=f"plaid/access-token/{user_id}"
        )
        token_data = json.loads(secret["SecretString"])
    except Exception:
        print(f"No bank connected for user {user_id}")
        return []

    try:
        creds_secret = secrets_client.get_secret_value(
            SecretId="plaid/credentials"
        )
        creds = json.loads(creds_secret["SecretString"])

        plaid_urls = {
            "sandbox": "https://sandbox.plaid.com",
            "production": "https://production.plaid.com",
        }

        base_url = plaid_urls.get(
            token_data.get("env", "sandbox"),
            plaid_urls["sandbox"],
        )

        try:
            center = (
                datetime.strptime(receipt_date, "%Y-%m-%d").date()
                if receipt_date
                else date.today()
            )
        except Exception:
            center = date.today()

        payload = json.dumps({
            "client_id": creds["clientId"],
            "secret": creds["secret"],
            "access_token": token_data["accessToken"],
            "start_date": (center - timedelta(days=90)).isoformat(),
            "end_date": (center + timedelta(days=90)).isoformat(),
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{base_url}/transactions/get",
            data=payload,
            headers={
                "Content-Type": "application/json"
            },
            method="POST",
        )

        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())

        return result.get("transactions", [])

    except Exception as error:
        print(f"Could not fetch Plaid transactions for user {user_id}: {str(error)}")
        return []


def match_transaction(extracted, transactions):
    if not transactions:
        return "UNMATCHED", 0.0, None

    receipt_amount = parse_amount(extracted.get("totalAmount"))

    if receipt_amount is None or receipt_amount <= 0:
        return "UNMATCHED", 0.0, None

    receipt_merchant = (extracted.get("merchantName") or "").lower().strip()

    best_match = None
    best_score = 0.0

    for txn in transactions:
        try:
            txn_amount = abs(float(txn.get("amount", 0)))
        except (ValueError, TypeError):
            continue

        txn_name = (
            txn.get("merchant_name")
            or txn.get("name")
            or ""
        ).lower().strip()

        amount_difference_ratio = abs(txn_amount - receipt_amount) / receipt_amount

        if amount_difference_ratio > 0.01:
            continue

        if receipt_merchant and txn_name:
            name_score = SequenceMatcher(
                None,
                receipt_merchant,
                txn_name,
            ).ratio()
        else:
            name_score = 0.0

        confidence = 0.6 + (name_score * 0.4)

        if confidence > best_score:
            best_score = confidence
            best_match = txn

    if best_match and best_score >= 0.75:
        status = "MATCHED"
    elif best_match and best_score >= 0.6:
        status = "POSSIBLE_MATCH"
    else:
        status = "UNMATCHED"

    return status, round(best_score, 2), best_match


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------

def handler(event, context):
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]

        # S3 event keys are URL-encoded.
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

        print(f"Processing receipt: bucket={bucket}, key={key}")

        parts = key.split("/")

        if len(parts) < 4:
            print(f"Invalid S3 key structure: {key}")
            continue

        user_id = parts[1]
        receipt_id = parts[2]

        # Mark as processing
        update_status(user_id, receipt_id, "PROCESSING", extra_fields={
            "s3ObjectKey": key,
            "createdAt": now_iso(),
        })

        try:
            # Step 1: Extract receipt data using Textract
            extracted_data = process_receipt_image(bucket, key)

            print(
                f"Extracted: merchant={extracted_data.get('merchantName')}, "
                f"total={extracted_data.get('totalAmount')}, "
                f"items={len(extracted_data.get('receiptItems', []))}, "
                f"category={extracted_data.get('category')}"
            )

            # Step 2: Attempt Plaid transaction matching
            transactions = get_plaid_transactions(
                user_id,
                extracted_data.get("receiptDate"),
            )

            match_status, confidence, matched_txn = match_transaction(
                extracted_data,
                transactions,
            )

            print(f"Transaction match: status={match_status}, confidence={confidence}")

            # Step 3: Build final record fields
            final_fields = {
                "s3ObjectKey": key,
                "merchantName": extracted_data.get("merchantName"),
                "receiptDate": extracted_data.get("receiptDate"),
                "receiptTime": extracted_data.get("receiptTime"),
                "totalAmount": extracted_data.get("totalAmount"),
                "subtotalAmount": extracted_data.get("subtotalAmount"),
                "taxAmount": extracted_data.get("taxAmount"),
                "tipAmount": extracted_data.get("tipAmount"),
                "currency": extracted_data.get("currency"),
                "category": extracted_data.get("category", "Other"),
                "receiptItems": extracted_data.get("receiptItems", []),
                "transactionMatchStatus": match_status,
                "matchConfidence": str(confidence),
            }

            if matched_txn:
                final_fields["matchedTransactionId"] = matched_txn.get(
                    "transaction_id", ""
                )
                final_fields["matchedTransactionName"] = matched_txn.get(
                    "name", ""
                )
                final_fields["matchedAmount"] = str(
                    abs(float(matched_txn.get("amount", 0)))
                )
                final_fields["matchedDate"] = matched_txn.get("date", "")

            # Remove None values to avoid storing empty fields
            final_fields = {
                k: v for k, v in final_fields.items() if v is not None
            }

            update_status(
                user_id,
                receipt_id,
                "COMPLETED",
                extra_fields=final_fields,
            )

        except Exception as error:
            print(f"Error processing {key}: {str(error)}")

            update_status(
                user_id,
                receipt_id,
                "FAILED",
                extra_fields={
                    "s3ObjectKey": key,
                    "errorMessage": str(error)[:500],
                },
            )