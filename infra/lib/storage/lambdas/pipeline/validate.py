"""
Stage 3: Validate normalized receipt data against financial consistency rules.

Reads the normalized JSON from S3 (normalizedDataKey).
Performs:
  - Field format validation (amounts, dates, times, currency)
  - Line arithmetic:   quantity × unitPrice ≈ lineTotal
  - Line coverage:     sum(lineTotal) ≈ subtotal
  - Receipt arithmetic: subtotal - discounts + tax + tip + serviceCharge ≈ total
  - Source confidence check from Textract fields

Sets repairRequired = True for recoverable issues.
Sets processingStatus = NEEDS_REVIEW when quality is too poor to accept or repair.
Saves full validation detail to S3 and returns a small summary through Step Functions.
"""

import json
import os
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import boto3

s3_client = boto3.client("s3")

BUCKET_NAME = os.environ["BUCKET_NAME"]

CATEGORIES = [
    "Groceries", "Dining", "Entertainment", "Transport",
    "Health", "Shopping", "Utilities", "Other",
]

# A receipt is accepted without repair if confidence ≥ this value.
REPAIR_THRESHOLD = 0.50
REVIEW_THRESHOLD = 0.30

# Relative tolerance for financial reconciliation checks (e.g. 2 %).
RECONCILIATION_TOLERANCE = Decimal("0.02")

# Absolute tolerance for rounding errors in currency (e.g. 0.05).
ROUNDING_TOLERANCE = Decimal("0.05")

# Textract field confidence below which we flag the item for repair.
LOW_CONFIDENCE_THRESHOLD = 80.0


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _within_tolerance(a: Decimal, b: Decimal, tolerance: Decimal) -> bool:
    """Return True if |a - b| ≤ tolerance * max(|a|, |b|, 1)."""
    diff = abs(a - b)
    base = max(abs(a), abs(b), Decimal("1"))
    return diff <= tolerance * base or diff <= ROUNDING_TOLERANCE


# ---------------------------------------------------------------------------
# Field validators
# ---------------------------------------------------------------------------

def validate_amount(value, field_name: str, allow_negative: bool = False) -> list[dict]:
    issues = []
    if value is None:
        return issues
    d = _to_decimal(value)
    if d is None:
        issues.append({"field": field_name, "issue": f"Invalid decimal: {value}", "severity": "error"})
        return issues
    if not allow_negative and d < 0:
        issues.append({"field": field_name, "issue": f"Negative amount not expected: {value}", "severity": "error"})
    if d > Decimal("1000000"):
        issues.append({"field": field_name, "issue": f"Unreasonably large amount: {value}", "severity": "error"})
    return issues


def validate_date(value) -> list[dict]:
    if value is None:
        return []
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(value)):
        return [{"field": "receiptDate", "issue": f"Invalid date format: {value}", "severity": "error"}]
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
        if parsed.year < 2000 or parsed.date() > datetime.now(timezone.utc).date():
            return [{"field": "receiptDate", "issue": f"Date out of reasonable range: {value}", "severity": "warning"}]
    except ValueError:
        return [{"field": "receiptDate", "issue": f"Invalid date: {value}", "severity": "error"}]
    return []


def validate_time(value) -> list[dict]:
    if value is None:
        return []
    if not re.match(r"^\d{2}:\d{2}:\d{2}$", str(value)):
        return [{"field": "receiptTime", "issue": f"Invalid time format: {value}", "severity": "error"}]
    try:
        datetime.strptime(value, "%H:%M:%S")
    except ValueError:
        return [{"field": "receiptTime", "issue": f"Invalid time: {value}", "severity": "error"}]
    return []


def validate_currency(value) -> list[dict]:
    if value is None:
        return []
    if not re.match(r"^[A-Z]{3}$", str(value)):
        return [{"field": "currency", "issue": f"Invalid ISO 4217 currency code: {value}", "severity": "warning"}]
    return []


# ---------------------------------------------------------------------------
# Financial consistency checks
# ---------------------------------------------------------------------------

def check_line_arithmetic(items: list[dict]) -> list[dict]:
    """quantity × unitPrice ≈ lineTotal for each item."""
    issues = []
    for i, item in enumerate(items):
        qty = _to_decimal(item.get("quantity"))
        unit_price = _to_decimal(item.get("unitPrice"))
        line_total = _to_decimal(item.get("lineTotal"))
        if qty is None or unit_price is None or line_total is None:
            continue
        try:
            expected = qty * unit_price
        except Exception:
            continue
        if not _within_tolerance(expected, line_total, RECONCILIATION_TOLERANCE):
            issues.append({
                "field": f"receiptItems[{i}]",
                "issue": (
                    f"Line arithmetic mismatch: {qty} × {unit_price} = {expected:.2f} "
                    f"but lineTotal = {line_total}"
                ),
                "severity": "warning",
                "repairHint": True,
            })
    return issues


def check_line_coverage(items: list[dict], subtotal) -> list[dict]:
    """sum(lineTotal) ≈ subtotal."""
    line_sum = Decimal("0")
    items_with_total = 0
    for item in items:
        lt = _to_decimal(item.get("lineTotal"))
        if lt is not None:
            line_sum += lt
            items_with_total += 1
    if items_with_total == 0 or subtotal is None:
        return []
    sub_d = _to_decimal(subtotal)
    if sub_d is None:
        return []
    if not _within_tolerance(line_sum, sub_d, RECONCILIATION_TOLERANCE):
        return [{
            "field": "lineCoverage",
            "issue": (
                f"Sum of line totals ({line_sum:.2f}) does not match "
                f"subtotal ({sub_d:.2f})"
            ),
            "severity": "warning",
            "repairHint": True,
        }]
    return []


def check_receipt_arithmetic(data: dict) -> list[dict]:
    """
    subtotal - discounts + tax + tip + serviceCharge ≈ total
    (with tolerances for rounding)
    """
    total = _to_decimal(data.get("totalAmount"))
    subtotal = _to_decimal(data.get("subtotalAmount"))
    tax = _to_decimal(data.get("taxAmount")) or Decimal("0")
    tip = _to_decimal(data.get("tipAmount")) or Decimal("0")
    discount = _to_decimal(data.get("discountAmount")) or Decimal("0")
    service = _to_decimal(data.get("serviceChargeAmount")) or Decimal("0")

    if total is None or subtotal is None:
        return []

    expected = subtotal - abs(discount) + tax + tip + service
    if not _within_tolerance(expected, total, RECONCILIATION_TOLERANCE):
        return [{
            "field": "receiptArithmetic",
            "issue": (
                f"Receipt arithmetic mismatch: subtotal({subtotal}) "
                f"- discount({discount}) + tax({tax}) + tip({tip}) "
                f"+ service({service}) = {expected:.2f}, "
                f"but total = {total}"
            ),
            "severity": "warning",
            "repairHint": True,
        }]
    return []


def check_item_structure(items: list[dict]) -> list[dict]:
    issues = []
    if not isinstance(items, list):
        return [{"field": "receiptItems", "issue": "Not a list", "severity": "error"}]
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            issues.append({"field": f"receiptItems[{i}]", "issue": "Not a dict", "severity": "error"})
            continue
        if not item.get("name") and not item.get("lineTotal") and not item.get("unitPrice"):
            issues.append({
                "field": f"receiptItems[{i}]",
                "issue": "Missing name, lineTotal, and unitPrice",
                "severity": "warning",
                "repairHint": True,
            })
        for amt_field in ("unitPrice", "lineTotal", "discount"):
            if item.get(amt_field) is not None:
                issues.extend(
                    validate_amount(item[amt_field], f"receiptItems[{i}].{amt_field}",
                                    allow_negative=(amt_field == "discount"))
                )
        conf = item.get("sourceConfidence")
        if conf is not None and float(conf) < LOW_CONFIDENCE_THRESHOLD / 100:
            issues.append({
                "field": f"receiptItems[{i}].sourceConfidence",
                "issue": f"Low Textract confidence: {conf:.0%}",
                "severity": "warning",
                "repairHint": True,
            })
    return issues


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def compute_confidence(data: dict, issues: list[dict]) -> float:
    """
    Score based on:
    - Presence of key summary fields (weighted)
    - Line coverage (has items with line totals)
    - Average Textract sourceConfidence across items
    - Arithmetic reconciliation (penalises mismatches)
    - Error/warning count
    """
    score = Decimal("0")

    weights = {
        "merchantName": Decimal("0.15"),
        "totalAmount": Decimal("0.25"),
        "receiptDate": Decimal("0.15"),
        "items_nonempty": Decimal("0.15"),
        "items_have_totals": Decimal("0.10"),
        "currency": Decimal("0.05"),
        "subtotalAmount": Decimal("0.05"),
        "taxAmount": Decimal("0.05"),
        "category_specific": Decimal("0.05"),
    }
    max_score = sum(weights.values())

    if data.get("merchantName"):
        score += weights["merchantName"]
    if data.get("totalAmount"):
        score += weights["totalAmount"]
    if data.get("receiptDate"):
        score += weights["receiptDate"]
    items = data.get("receiptItems", [])
    if items:
        score += weights["items_nonempty"]
        if any(item.get("lineTotal") for item in items):
            score += weights["items_have_totals"]
    if data.get("currency"):
        score += weights["currency"]
    if data.get("subtotalAmount"):
        score += weights["subtotalAmount"]
    if data.get("taxAmount"):
        score += weights["taxAmount"]
    if data.get("category") not in (None, "Other"):
        score += weights["category_specific"]

    # Incorporate average Textract field confidence.
    confidences = [
        item["sourceConfidence"]
        for item in items
        if item.get("sourceConfidence") is not None
    ]
    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        # Scale: if avg_conf = 1.0 → no penalty; if 0.5 → subtract 0.1
        conf_penalty = Decimal(str(max(0.0, (1.0 - avg_conf) * 0.2)))
        score -= conf_penalty

    errors = [i for i in issues if i.get("severity") == "error"]
    warnings = [i for i in issues if i.get("severity") == "warning"]
    score -= Decimal(str(len(errors) * 0.12 + len(warnings) * 0.04))
    score = max(Decimal("0"), score)

    return round(float(score / max_score), 2)


# ---------------------------------------------------------------------------
# Repair reasons builder
# ---------------------------------------------------------------------------

def _repair_reasons(issues: list[dict], data: dict) -> list[str]:
    reasons = []
    items = data.get("receiptItems", [])
    if not items and data.get("totalAmount"):
        reasons.append("No line items extracted but receipt has a positive total")
    if any(i.get("repairHint") for i in issues):
        for i in issues:
            if i.get("repairHint"):
                reasons.append(i["issue"])
    return reasons


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------

def handler(event, context):
    """
    Reads normalizedDataKey from event, validates, saves validation.json to S3.
    Returns small summary + repairRequired flag through Step Functions.
    """
    user_id = event["userId"]
    receipt_id = event["receiptId"]
    normalized_key = event["normalizedDataKey"]
    repair_attempted = event.get("repairAttempted", False)

    print(f"[Validate] Validating receipt {receipt_id} (repairAttempted={repair_attempted})")

    obj = s3_client.get_object(Bucket=BUCKET_NAME, Key=normalized_key)
    data = json.loads(obj["Body"].read())

    issues: list[dict] = []

    # Amount fields — discountAmount is allowed to be negative.
    for field, allow_neg in [
        ("totalAmount", False), ("subtotalAmount", False),
        ("taxAmount", False), ("tipAmount", False),
        ("discountAmount", True), ("serviceChargeAmount", False),
    ]:
        issues.extend(validate_amount(data.get(field), field, allow_neg))

    issues.extend(validate_date(data.get("receiptDate")))
    issues.extend(validate_time(data.get("receiptTime")))
    issues.extend(validate_currency(data.get("currency")))

    if data.get("category") not in CATEGORIES:
        issues.append({
            "field": "category",
            "issue": f"Invalid category: {data.get('category')}",
            "severity": "warning",
        })
        data["category"] = "Other"

    items = data.get("receiptItems", [])
    issues.extend(check_item_structure(items))
    issues.extend(check_line_arithmetic(items))
    issues.extend(check_line_coverage(items, data.get("subtotalAmount")))
    issues.extend(check_receipt_arithmetic(data))

    if data.get("itemsTruncated"):
        issues.append({
            "field": "receiptItems",
            "issue": "Line item list was truncated during extraction",
            "severity": "warning",
        })

    confidence = compute_confidence(data, issues)
    errors = [i for i in issues if i.get("severity") == "error"]
    warnings = [i for i in issues if i.get("severity") != "error"]

    repair_reasons = _repair_reasons(issues, data)

    # Decide processing status.
    repair_required = (
        not repair_attempted
        and bool(repair_reasons)
        and confidence >= REVIEW_THRESHOLD
    )

    if confidence < REVIEW_THRESHOLD or len(errors) > 3:
        processing_status = "NEEDS_REVIEW"
        repair_required = False  # too low quality to attempt repair
    elif repair_required:
        processing_status = "NEEDS_REPAIR"
    else:
        processing_status = "COMPLETED"

    print(
        f"[Validate] confidence={confidence}, errors={len(errors)}, "
        f"warnings={len(warnings)}, repairRequired={repair_required}, "
        f"status={processing_status}"
    )

    validation_result = {
        "confidence": confidence,
        "issues": issues,
        "errorCount": len(errors),
        "warningCount": len(warnings),
        "repairReasons": repair_reasons,
    }

    # Save full validation detail to S3.
    validation_key = f"raw-extractions/{user_id}/{receipt_id}/validation.json"
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=validation_key,
        Body=json.dumps(
            {
                "validationResult": validation_result,
                "normalizedDataKey": normalized_key,
                "validatedAt": now_iso(),
                "repairAttempted": repair_attempted,
            },
            default=str,
        ),
        ContentType="application/json",
    )

    # Return only the summary through Step Functions.
    return {
        **event,
        "validationKey": validation_key,
        "repairRequired": repair_required,
        "processingStatus": processing_status,
        "validationSummary": {
            "confidence": confidence,
            "errorCount": len(errors),
            "warningCount": len(warnings),
        },
        "validatedAt": now_iso(),
    }

