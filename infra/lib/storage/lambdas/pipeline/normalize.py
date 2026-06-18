"""
Stage 2: Normalize Textract AnalyzeExpense output into canonical receipt schema.

Maps Textract expense fields deterministically. Reads the category that was
already classified by the extraction stage (Bedrock vision call) so no
additional model call is needed here.
"""

import os
import re
from datetime import datetime, timezone

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

EXPENSE_FIELD_MAP = {
    "VENDOR_NAME": "merchantName",
    "VENDOR_ADDRESS": "merchantAddress",
    "INVOICE_RECEIPT_DATE": "receiptDate",
    "INVOICE_RECEIPT_TIME": "receiptTime",
    "TOTAL": "totalAmount",
    "SUBTOTAL": "subtotalAmount",
    "TAX": "taxAmount",
    "GRATUITY": "tipAmount",
    "TIP": "tipAmount",
    "PAYMENT_TERMS": "paymentMethod",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def clean_amount(value):
    """Strip currency symbols and normalize decimal separator."""
    if not value:
        return None

    cleaned = re.sub(r"[^\d.,\-]", "", str(value))
    cleaned = cleaned.replace(",", ".")

    parts = cleaned.split(".")
    if len(parts) > 2:
        cleaned = "".join(parts[:-1]) + "." + parts[-1]

    try:
        amount = float(cleaned)
        if amount < 0:
            return None
        return f"{amount:.2f}"
    except (ValueError, TypeError):
        return None


def normalize_date(value):
    """Try to parse date into YYYY-MM-DD format."""
    if not value:
        return None

    date_formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d.%m.%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d, %Y",
        "%B %d, %Y",
    ]

    cleaned = str(value).strip()

    for fmt in date_formats:
        try:
            parsed = datetime.strptime(cleaned, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return cleaned if re.match(r"\d{4}-\d{2}-\d{2}", cleaned) else None


def normalize_time(value):
    """Try to parse time into HH:MM:SS format."""
    if not value:
        return None

    cleaned = str(value).strip()

    time_formats = ["%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p"]

    for fmt in time_formats:
        try:
            parsed = datetime.strptime(cleaned, fmt)
            return parsed.strftime("%H:%M:%S")
        except ValueError:
            continue

    if re.match(r"\d{2}:\d{2}(:\d{2})?", cleaned):
        return cleaned if len(cleaned) == 8 else cleaned + ":00"

    return None


def detect_currency(textract_result):
    """Try to detect currency from Textract expense data."""
    for doc in textract_result.get("ExpenseDocuments", []):
        for field in doc.get("SummaryFields", []):
            if field.get("Currency", {}).get("Code"):
                return field["Currency"]["Code"]

            value_text = field.get("ValueDetection", {}).get("Text", "")
            if "CHF" in value_text:
                return "CHF"
            elif "€" in value_text or "EUR" in value_text:
                return "EUR"
            elif "$" in value_text or "USD" in value_text:
                return "USD"
            elif "£" in value_text or "GBP" in value_text:
                return "GBP"

    return None


def extract_summary_fields(textract_result):
    """Extract summary fields from Textract AnalyzeExpense output."""
    result = {}

    for doc in textract_result.get("ExpenseDocuments", []):
        for field in doc.get("SummaryFields", []):
            field_type = field.get("Type", {}).get("Text", "")
            value = field.get("ValueDetection", {}).get("Text", "")

            if not value:
                continue

            canonical_key = EXPENSE_FIELD_MAP.get(field_type)
            if canonical_key and canonical_key not in result:
                result[canonical_key] = value

    return result


def extract_line_items(textract_result):
    """Extract line items from Textract AnalyzeExpense output."""
    items = []

    for doc in textract_result.get("ExpenseDocuments", []):
        for group in doc.get("LineItemGroups", []):
            for line_item in group.get("LineItems", []):
                item = {}
                for field in line_item.get("LineItemExpenseFields", []):
                    field_type = field.get("Type", {}).get("Text", "")
                    value = field.get("ValueDetection", {}).get("Text", "")

                    if field_type == "ITEM":
                        item["name"] = value
                    elif field_type == "QUANTITY":
                        item["quantity"] = value
                    elif field_type == "PRICE":
                        item["price"] = clean_amount(value)
                    elif field_type == "UNIT_PRICE":
                        if "price" not in item:
                            item["price"] = clean_amount(value)

                if item.get("name") or item.get("price"):
                    items.append(item)

    return items[:50]


def get_category_from_extraction(raw_category):
    """Return the category extracted by the OCR stage, falling back to 'Other'."""
    if raw_category in CATEGORIES:
        return raw_category
    if raw_category:
        for cat in CATEGORIES:
            if cat.lower() in str(raw_category).lower():
                return cat
    return "Other"


def handler(event, context):
    """
    Input: event from extract_ocr stage with textractResult.
    Output: event with normalized receipt data in canonical schema.
    """
    textract_result = event.get("textractResult", {})
    user_id = event["userId"]
    receipt_id = event["receiptId"]

    print(f"[Normalize] Processing receipt {receipt_id} for user {user_id}")

    summary = extract_summary_fields(textract_result)
    line_items = extract_line_items(textract_result)
    currency = detect_currency(textract_result)

    normalized = {
        "merchantName": (summary.get("merchantName") or "")[:200] or None,
        "merchantAddress": (summary.get("merchantAddress") or "")[:500] or None,
        "receiptDate": normalize_date(summary.get("receiptDate")),
        "receiptTime": normalize_time(summary.get("receiptTime")),
        "totalAmount": clean_amount(summary.get("totalAmount")),
        "subtotalAmount": clean_amount(summary.get("subtotalAmount")),
        "taxAmount": clean_amount(summary.get("taxAmount")),
        "tipAmount": clean_amount(summary.get("tipAmount")),
        "currency": currency,
        "paymentMethod": (summary.get("paymentMethod") or "")[:50] or None,
        "receiptItems": [
            {
                "name": (item.get("name") or "")[:200] or None,
                "quantity": item.get("quantity"),
                "price": item.get("price"),
            }
            for item in line_items
        ],
    }

    category = get_category_from_extraction(
        event.get("rawCategory"),
    )
    normalized["category"] = category

    print(
        f"[Normalize] Extracted: merchant={normalized.get('merchantName')}, "
        f"total={normalized.get('totalAmount')}, "
        f"items={len(normalized.get('receiptItems', []))}, "
        f"category={category}"
    )

    output = {
        "bucket": event["bucket"],
        "key": event["key"],
        "userId": user_id,
        "receiptId": receipt_id,
        "rawExtractionKey": event["rawExtractionKey"],
        "extractedAt": event["extractedAt"],
        "normalizedData": normalized,
        "normalizedAt": now_iso(),
    }

    return output
