"""
Stage 2: Normalize Textract AnalyzeExpense output into the canonical receipt schema.

Reads the raw Textract JSON from S3 (textractKey) and maps fields deterministically.
Uses Decimal for all monetary arithmetic. Implements a deterministic keyword-based
category classifier — no Bedrock call needed here.

Canonical line-item schema:
  name, quantity, unit, unitPrice, lineTotal, discount, productCode,
  rawText, sourceConfidence
"""

import json
import os
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import boto3

s3_client = boto3.client("s3")

BUCKET_NAME = os.environ["BUCKET_NAME"]

# Maximum line items to store (full raw Textract is already in S3).
MAX_LINE_ITEMS = 100

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

# Summary-field Textract type → canonical schema key
SUMMARY_FIELD_MAP = {
    "VENDOR_NAME": "merchantName",
    "VENDOR_ADDRESS": "merchantAddress",
    "INVOICE_RECEIPT_DATE": "receiptDate",
    "INVOICE_RECEIPT_TIME": "receiptTime",
    "TOTAL": "totalAmount",
    "SUBTOTAL": "subtotalAmount",
    "TAX": "taxAmount",
    "GRATUITY": "tipAmount",
    "TIP": "tipAmount",
    "SERVICE_CHARGE": "serviceChargeAmount",
    "DISCOUNT": "discountAmount",
    "PAYMENT_TERMS": "paymentMethod",
    "RECEIVER_NAME": "merchantName",  # fallback
}

# Category keyword rules: (keywords in merchant name or item names) → category
_CATEGORY_RULES: list[tuple[list[str], str]] = [
    (["restaurant", "café", "cafe", "bistro", "pizzeria", "sushi",
      "burger", "grill", "diner", "bakery", "bäckerei", "boulangerie"], "Dining"),
    (["supermarket", "grocery", "grocer", "lidl", "aldi", "rewe",
      "migros", "coop", "spar", "edeka", "carrefour", "sainsbury",
      "tesco", "whole foods", "market", "lebensmittel", "épicerie"], "Groceries"),
    (["pharmacy", "apotheke", "pharmacie", "drug", "chemist",
      "hospital", "clinic", "arzt", "doctor", "dental", "medical",
      "gesundheit", "health"], "Health"),
    (["uber", "lyft", "taxi", "transport", "train", "bus", "metro",
      "subway", "bahn", "sbb", "öbb", "railjet", "ryanair", "easyjet",
      "lufthansa", "airline", "parking", "garage"], "Transport"),
    (["cinema", "theater", "theatre", "concert", "museum", "sport",
      "fitness", "gym", "kino", "bowling", "netflix", "spotify",
      "event", "ticket"], "Entertainment"),
    (["electricity", "gas", "water", "internet", "phone", "telekom",
      "vodafone", "swisscom", "a1", "utility", "utilities", "strom",
      "energie", "energie"], "Utilities"),
    (["amazon", "zalando", "h&m", "zara", "ikea", "saturn", "media markt",
      "electronics", "clothing", "apparel", "shoe", "fashion",
      "department", "store", "shop"], "Shopping"),
]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Amount parsing
# ---------------------------------------------------------------------------

def parse_decimal(value: str | None) -> Decimal | None:
    """
    Parse a monetary string into a Decimal, handling:
      - Currency symbols / prefixes (€, $, CHF, …)
      - European comma-decimals: 1,49 → 1.49
      - Thousands separators: 1.234,56 → 1234.56
      - Negative amounts: -0.40, (0.40)
      - Trailing signs: 1.49-
    Returns None if the value cannot be parsed.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    # Remove currency symbols and letter prefixes (€, $, £, CHF, EUR, …)
    text = re.sub(r"[€£$¥₹]", "", text)
    text = re.sub(r"^[A-Z]{2,3}\s*", "", text)  # e.g. "CHF 12.50"
    text = text.strip()

    # Handle accounting negatives like (1.50)
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1].strip()

    # Trailing minus sign (some POS formats)
    if text.endswith("-"):
        negative = True
        text = text[:-1].strip()

    if text.startswith("-"):
        negative = True
        text = text[1:].strip()

    # Strip any remaining non-numeric chars except . and ,
    text = re.sub(r"[^\d.,]", "", text)
    if not text:
        return None

    # Disambiguate European vs US number formats.
    # Rules:
    #   "1.234,56" → European thousands (period = thousands, comma = decimal)
    #   "1,234.56" → US thousands (comma = thousands, period = decimal)
    #   "1,49"     → European decimal (no thousands separator)
    #   "1.49"     → US/standard decimal
    dot_count = text.count(".")
    comma_count = text.count(",")

    if dot_count == 1 and comma_count == 1:
        # Mixed separators — determine which is the decimal.
        dot_pos = text.rindex(".")
        comma_pos = text.rindex(",")
        if comma_pos > dot_pos:
            # European: 1.234,56
            text = text.replace(".", "").replace(",", ".")
        else:
            # US: 1,234.56
            text = text.replace(",", "")
    elif comma_count >= 1 and dot_count == 0:
        # European: 1,49 or 1.234.567 (dots as thousands, but no dot here)
        parts = text.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            # Decimal comma: 1,49
            text = text.replace(",", ".")
        else:
            # Thousands separator only: remove commas
            text = text.replace(",", "")
    elif dot_count >= 2:
        # Multiple dots → all are thousands separators; remove them entirely.
        parts = text.split(".")
        text = "".join(parts)
    elif comma_count >= 2:
        text = text.replace(",", "")

    try:
        result = Decimal(text)
        return -result if negative else result
    except InvalidOperation:
        return None


def format_decimal(value: Decimal | None) -> str | None:
    """Format a Decimal as a 2-decimal-place string, or None."""
    if value is None:
        return None
    return f"{value:.2f}"


# ---------------------------------------------------------------------------
# Date / time normalisation
# ---------------------------------------------------------------------------

_DATE_FORMATS = [
    "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
    "%d.%m.%Y", "%d-%m-%Y", "%Y/%m/%d",
    "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y",
]

_TIME_FORMATS = ["%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p"]


def normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return cleaned if re.match(r"\d{4}-\d{2}-\d{2}", cleaned) else None


def normalize_time(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = str(value).strip()
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).strftime("%H:%M:%S")
        except ValueError:
            continue
    if re.match(r"\d{2}:\d{2}(:\d{2})?", cleaned):
        return cleaned if len(cleaned) == 8 else cleaned + ":00"
    return None


# ---------------------------------------------------------------------------
# Currency detection
# ---------------------------------------------------------------------------

def detect_currency(expense_docs: list) -> str | None:
    for doc in expense_docs:
        for field in doc.get("SummaryFields", []):
            code = field.get("Currency", {}).get("Code")
            if code:
                return code
            text = field.get("ValueDetection", {}).get("Text", "")
            if "CHF" in text:
                return "CHF"
            if "€" in text or "EUR" in text:
                return "EUR"
            if "$" in text or "USD" in text:
                return "USD"
            if "£" in text or "GBP" in text:
                return "GBP"
    return None


# ---------------------------------------------------------------------------
# Textract → canonical field extraction
# ---------------------------------------------------------------------------

def extract_summary(expense_docs: list) -> dict:
    """Map Textract SummaryFields to the canonical schema."""
    result: dict = {}
    for doc in expense_docs:
        for field in doc.get("SummaryFields", []):
            field_type = field.get("Type", {}).get("Text", "")
            value = field.get("ValueDetection", {}).get("Text", "")
            if not value:
                continue
            key = SUMMARY_FIELD_MAP.get(field_type)
            if key and key not in result:
                result[key] = value
    return result


def extract_line_items(expense_docs: list) -> list[dict]:
    """
    Map Textract LineItems to canonical item objects.

    Textract field types:
      ITEM         → name
      QUANTITY     → quantity
      UNIT_PRICE   → unitPrice   (do NOT merge with lineTotal)
      PRICE        → lineTotal
      PRODUCT_CODE → productCode
      UNIT         → unit
      EXPENSE_ROW  → rawText (full row text if available)
    """
    items: list[dict] = []
    total_raw = 0

    for doc in expense_docs:
        for group in doc.get("LineItemGroups", []):
            for row in group.get("LineItems", []):
                item: dict = {}
                confidences: list[float] = []

                for field in row.get("LineItemExpenseFields", []):
                    ftype = field.get("Type", {}).get("Text", "")
                    value = (field.get("ValueDetection") or {}).get("Text", "") or ""
                    conf = (field.get("ValueDetection") or {}).get("Confidence")
                    if conf is not None:
                        confidences.append(float(conf))

                    if ftype == "ITEM":
                        item["name"] = value[:200]
                    elif ftype == "QUANTITY":
                        item["quantity"] = value
                    elif ftype == "UNIT":
                        item["unit"] = value
                    elif ftype == "UNIT_PRICE":
                        item["unitPrice"] = format_decimal(parse_decimal(value))
                    elif ftype == "PRICE":
                        item["lineTotal"] = format_decimal(parse_decimal(value))
                    elif ftype == "PRODUCT_CODE":
                        item["productCode"] = value
                    elif ftype == "EXPENSE_ROW":
                        item["rawText"] = value[:500]

                if item.get("name") or item.get("lineTotal") or item.get("unitPrice"):
                    if confidences:
                        item["sourceConfidence"] = round(min(confidences) / 100.0, 4)
                    items.append(item)
                    total_raw += 1

    truncated = total_raw > MAX_LINE_ITEMS
    if truncated:
        print(
            f"[Normalize] WARNING: {total_raw} line items extracted from Textract; "
            f"storing only the first {MAX_LINE_ITEMS}."
        )

    return items[:MAX_LINE_ITEMS], truncated


# ---------------------------------------------------------------------------
# Category classification (deterministic, no Bedrock)
# ---------------------------------------------------------------------------

def classify_category(merchant_name: str | None, items: list[dict]) -> str:
    """
    Assign a category using keyword matching against the merchant name
    and item names. No external model call.
    """
    candidate_text = " ".join(
        filter(None, [
            (merchant_name or "").lower(),
            *(item.get("name", "").lower() for item in (items or [])[:20]),
        ])
    )

    for keywords, category in _CATEGORY_RULES:
        for kw in keywords:
            if kw in candidate_text:
                return category

    return "Other"


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------

def handler(event, context):
    """
    Reads raw Textract JSON from S3 (event['textractKey']).
    Produces normalized receipt data and saves it to S3.
    Returns only the S3 key through Step Functions.
    """
    bucket = event["bucket"]
    user_id = event["userId"]
    receipt_id = event["receiptId"]
    textract_key = event["textractKey"]

    print(f"[Normalize] Processing receipt {receipt_id} for user {user_id}")

    # Load Textract output from S3.
    obj = s3_client.get_object(Bucket=BUCKET_NAME, Key=textract_key)
    textract_data = json.loads(obj["Body"].read())
    expense_docs = textract_data.get("ExpenseDocuments", [])

    summary = extract_summary(expense_docs)
    line_items, truncated = extract_line_items(expense_docs)
    currency = detect_currency(expense_docs)

    # Parse all monetary summary fields as Decimal, preserve negatives.
    total_amount_d = parse_decimal(summary.get("totalAmount"))
    subtotal_d = parse_decimal(summary.get("subtotalAmount"))
    tax_d = parse_decimal(summary.get("taxAmount"))
    tip_d = parse_decimal(summary.get("tipAmount"))
    discount_d = parse_decimal(summary.get("discountAmount"))
    service_charge_d = parse_decimal(summary.get("serviceChargeAmount"))

    merchant_name = (summary.get("merchantName") or "")[:200] or None
    category = classify_category(merchant_name, line_items)

    normalized = {
        "merchantName": merchant_name,
        "merchantAddress": (summary.get("merchantAddress") or "")[:500] or None,
        "receiptDate": normalize_date(summary.get("receiptDate")),
        "receiptTime": normalize_time(summary.get("receiptTime")),
        "totalAmount": format_decimal(total_amount_d),
        "subtotalAmount": format_decimal(subtotal_d),
        "taxAmount": format_decimal(tax_d),
        "tipAmount": format_decimal(tip_d),
        "discountAmount": format_decimal(discount_d),
        "serviceChargeAmount": format_decimal(service_charge_d),
        "currency": currency,
        "paymentMethod": (summary.get("paymentMethod") or "")[:50] or None,
        "category": category,
        "receiptItems": line_items,
        "itemsTruncated": truncated,
    }

    normalized_key = f"raw-extractions/{user_id}/{receipt_id}/normalized.json"
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=normalized_key,
        Body=json.dumps(normalized, default=str),
        ContentType="application/json",
    )

    print(
        f"[Normalize] merchant={merchant_name}, "
        f"total={normalized.get('totalAmount')}, "
        f"items={len(line_items)}, category={category}"
    )

    # Pass only keys + small metadata through Step Functions.
    return {
        "bucket": event["bucket"],
        "key": event["key"],
        "normalizedInputKey": event.get("normalizedInputKey"),
        "userId": user_id,
        "receiptId": receipt_id,
        "textractKey": textract_key,
        "normalizedDataKey": normalized_key,
        "extractedAt": event.get("extractedAt"),
        "normalizedAt": now_iso(),
    }

