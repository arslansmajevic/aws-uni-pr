"""
Stage 4 (final): Save the validated receipt to DynamoDB.

Uses update_item (not put_item) so that fields set by manual review
(manualOverrides, reviewedAt, reviewedBy) are never overwritten by a
pipeline retry.

Reads normalized data and the validation summary from S3 to stay within
the Step Functions payload limit.
"""

import json
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["RECEIPTS_TABLE_NAME"])
s3_client = boto3.client("s3")

BUCKET_NAME = os.environ["BUCKET_NAME"]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


def _sanitize(value):
    """Recursively convert floats → Decimal for DynamoDB compatibility."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(i) for i in value]
    return value


def handler(event, context):
    user_id = event["userId"]
    receipt_id = event["receiptId"]
    processing_status = event.get("processingStatus", "COMPLETED")
    normalized_key = event["normalizedDataKey"]
    validation_key = event.get("validationKey")

    print(f"[Save] Saving receipt {receipt_id} with status {processing_status}")

    # Load normalized data from S3.
    norm_obj = s3_client.get_object(Bucket=BUCKET_NAME, Key=normalized_key)
    normalized = json.loads(norm_obj["Body"].read())

    # Load validation summary from S3 if available.
    validation_result = {}
    if validation_key:
        try:
            val_obj = s3_client.get_object(Bucket=BUCKET_NAME, Key=validation_key)
            val_data = json.loads(val_obj["Body"].read())
            validation_result = val_data.get("validationResult", {})
        except Exception as exc:
            print(f"[Save] Warning: could not load validation data: {exc}")

    confidence_d = _to_decimal(
        event.get("validationSummary", {}).get("confidence")
        or validation_result.get("confidence", 0)
    )

    # Build UpdateExpression — never touch manualOverrides / reviewedAt / reviewedBy.
    fields = {
        "processingStatus": processing_status,
        "s3ObjectKey": event["key"],
        "textractKey": event.get("textractKey"),
        "normalizedDataKey": normalized_key,
        "layoutKey": event.get("layoutKey"),
        "repairKey": event.get("repairKey"),
        "validationKey": validation_key,
        "merchantName": normalized.get("merchantName"),
        "merchantAddress": normalized.get("merchantAddress"),
        "receiptDate": normalized.get("receiptDate"),
        "receiptTime": normalized.get("receiptTime"),
        "totalAmount": normalized.get("totalAmount"),
        "subtotalAmount": normalized.get("subtotalAmount"),
        "taxAmount": normalized.get("taxAmount"),
        "tipAmount": normalized.get("tipAmount"),
        "discountAmount": normalized.get("discountAmount"),
        "serviceChargeAmount": normalized.get("serviceChargeAmount"),
        "currency": normalized.get("currency"),
        "paymentMethod": normalized.get("paymentMethod"),
        "category": normalized.get("category", "Other"),
        "receiptItems": normalized.get("receiptItems", []),
        "confidence": str(confidence_d) if confidence_d is not None else "0",
        "validationErrors": validation_result.get("errorCount", 0),
        "validationWarnings": validation_result.get("warningCount", 0),
        "extractedAt": event.get("extractedAt"),
        "normalizedAt": event.get("normalizedAt"),
        "validatedAt": event.get("validatedAt"),
        "repairApplied": normalized.get("repairApplied", False),
        "repairPatchCount": normalized.get("repairPatchCount", 0),
        "updatedAt": now_iso(),
    }

    # Remove None values — DynamoDB cannot store them.
    fields = {k: v for k, v in fields.items() if v is not None}
    fields = _sanitize(fields)

    # Build a dynamic UpdateExpression from the fields dict.
    set_parts = []
    names = {}
    values = {}
    for i, (k, v) in enumerate(fields.items()):
        alias_name = f"#f{i}"
        alias_val = f":v{i}"
        names[alias_name] = k
        values[alias_val] = v
        set_parts.append(f"{alias_name} = {alias_val}")

    update_expr = "SET " + ", ".join(set_parts)

    table.update_item(
        Key={"userId": user_id, "receiptId": receipt_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )

    print(
        f"[Save] Receipt {receipt_id} saved. "
        f"status={processing_status}, confidence={confidence_d}"
    )

    return {
        "userId": user_id,
        "receiptId": receipt_id,
        "processingStatus": processing_status,
        "confidence": str(confidence_d) if confidence_d is not None else "0",
    }

