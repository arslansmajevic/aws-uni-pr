"""
Stage 3: Deterministic validation of normalized receipt data.

Applies rules-based validation, computes a confidence score,
and decides whether the receipt is COMPLETED or NEEDS_REVIEW.
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

REVIEW_THRESHOLD = 0.5


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def validate_amount(value):
    """Validate that a value is a valid positive decimal amount."""
    if value is None:
        return True, None

    try:
        amount = float(value)
        if amount < 0:
            return False, f"Negative amount: {value}"
        if amount > 1_000_000:
            return False, f"Unreasonably large amount: {value}"
        return True, None
    except (ValueError, TypeError):
        return False, f"Invalid amount format: {value}"


def validate_date(value):
    """Validate YYYY-MM-DD format and reasonable date range."""
    if value is None:
        return True, None

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(value)):
        return False, f"Invalid date format: {value}"

    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
        if parsed.year < 2000 or parsed > datetime.now():
            return False, f"Date out of reasonable range: {value}"
        return True, None
    except ValueError:
        return False, f"Invalid date: {value}"


def validate_time(value):
    """Validate HH:MM:SS format."""
    if value is None:
        return True, None

    if not re.match(r"^\d{2}:\d{2}:\d{2}$", str(value)):
        return False, f"Invalid time format: {value}"

    try:
        datetime.strptime(value, "%H:%M:%S")
        return True, None
    except ValueError:
        return False, f"Invalid time: {value}"


def validate_items(items):
    """Validate line items structure."""
    issues = []

    if not isinstance(items, list):
        return [{"field": "receiptItems", "issue": "Not a list"}]

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            issues.append({"field": f"receiptItems[{i}]", "issue": "Not a dict"})
            continue

        if not item.get("name") and not item.get("price"):
            issues.append(
                {"field": f"receiptItems[{i}]", "issue": "Missing name and price"}
            )

        if item.get("price"):
            valid, msg = validate_amount(item["price"])
            if not valid:
                issues.append({"field": f"receiptItems[{i}].price", "issue": msg})

    return issues


def check_total_consistency(data):
    """Check if item prices roughly sum to the total."""
    total = data.get("totalAmount")
    items = data.get("receiptItems", [])

    if not total or not items:
        return None

    try:
        total_val = float(total)
    except (ValueError, TypeError):
        return None

    item_sum = 0.0
    items_with_price = 0

    for item in items:
        if item.get("price"):
            try:
                item_sum += float(item["price"])
                items_with_price += 1
            except (ValueError, TypeError):
                pass

    if items_with_price == 0:
        return None

    if total_val > 0:
        diff_ratio = abs(item_sum - total_val) / total_val
        if diff_ratio > 0.3:
            return {
                "field": "totalConsistency",
                "issue": (
                    f"Item sum ({item_sum:.2f}) differs from "
                    f"total ({total_val:.2f}) by {diff_ratio:.0%}"
                ),
                "severity": "warning",
            }

    return None


def compute_confidence(data, validation_issues):
    """
    Compute a confidence score from 0.0 to 1.0 based on
    how much data was extracted and its consistency.
    """
    score = 0.0
    max_score = 0.0

    checks = [
        ("merchantName", 0.15),
        ("totalAmount", 0.25),
        ("receiptDate", 0.15),
        ("receiptItems_nonempty", 0.20),
        ("category_valid", 0.10),
        ("currency", 0.05),
        ("subtotalAmount", 0.05),
        ("taxAmount", 0.05),
    ]

    for field, weight in checks:
        max_score += weight

        if field == "receiptItems_nonempty":
            if data.get("receiptItems") and len(data["receiptItems"]) > 0:
                score += weight
        elif field == "category_valid":
            if data.get("category") in CATEGORIES and data["category"] != "Other":
                score += weight
        else:
            if data.get(field):
                score += weight

    error_count = len([i for i in validation_issues if i.get("severity") != "warning"])
    warning_count = len([i for i in validation_issues if i.get("severity") == "warning"])

    penalty = (error_count * 0.15) + (warning_count * 0.05)
    score = max(0.0, score - penalty)

    return round(score / max_score, 2) if max_score > 0 else 0.0


def handler(event, context):
    """
    Input: event from normalize stage with normalizedData.
    Output: event with validation results and processing status.
    """
    normalized = event.get("normalizedData", {})
    user_id = event["userId"]
    receipt_id = event["receiptId"]

    print(f"[Validate] Validating receipt {receipt_id}")

    validation_issues = []

    amount_fields = ["totalAmount", "subtotalAmount", "taxAmount", "tipAmount"]
    for field in amount_fields:
        valid, msg = validate_amount(normalized.get(field))
        if not valid:
            validation_issues.append({"field": field, "issue": msg})

    valid, msg = validate_date(normalized.get("receiptDate"))
    if not valid:
        validation_issues.append({"field": "receiptDate", "issue": msg})

    valid, msg = validate_time(normalized.get("receiptTime"))
    if not valid:
        validation_issues.append({"field": "receiptTime", "issue": msg})

    if normalized.get("category") not in CATEGORIES:
        validation_issues.append(
            {"field": "category", "issue": f"Invalid category: {normalized.get('category')}"}
        )
        normalized["category"] = "Other"

    item_issues = validate_items(normalized.get("receiptItems", []))
    validation_issues.extend(item_issues)

    consistency_issue = check_total_consistency(normalized)
    if consistency_issue:
        validation_issues.append(consistency_issue)

    confidence = compute_confidence(normalized, validation_issues)

    error_issues = [i for i in validation_issues if i.get("severity") != "warning"]

    if confidence < REVIEW_THRESHOLD or len(error_issues) > 2:
        processing_status = "NEEDS_REVIEW"
    else:
        processing_status = "COMPLETED"

    print(
        f"[Validate] confidence={confidence}, "
        f"issues={len(validation_issues)}, "
        f"errors={len(error_issues)}, "
        f"status={processing_status}"
    )

    output = {
        "bucket": event["bucket"],
        "key": event["key"],
        "userId": user_id,
        "receiptId": receipt_id,
        "rawExtractionKey": event["rawExtractionKey"],
        "extractedAt": event["extractedAt"],
        "normalizedAt": event["normalizedAt"],
        "normalizedData": normalized,
        "validationResult": {
            "confidence": confidence,
            "issues": validation_issues,
            "errorCount": len(error_issues),
            "warningCount": len(validation_issues) - len(error_issues),
        },
        "processingStatus": processing_status,
        "validatedAt": now_iso(),
    }

    return output
