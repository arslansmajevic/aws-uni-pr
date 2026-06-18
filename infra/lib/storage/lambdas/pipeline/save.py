"""
Stage 4: Save the validated receipt to DynamoDB.

Writes the final structured receipt record with all metadata
including raw extraction reference, validation results, and
processing status.
"""

import os
import json
import boto3
from decimal import Decimal
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["RECEIPTS_TABLE_NAME"])
s3_client = boto3.client("s3")

BUCKET_NAME = os.environ["BUCKET_NAME"]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def sanitize_for_dynamodb(value):
    """Convert floats to Decimal and handle nested structures for DynamoDB."""
    if isinstance(value, float):
        return Decimal(str(value))

    if isinstance(value, dict):
        return {k: sanitize_for_dynamodb(v) for k, v in value.items()}

    if isinstance(value, list):
        return [sanitize_for_dynamodb(item) for item in value]

    return value


def handler(event, context):
    """
    Input: event from validate stage with all pipeline data.
    Output: final receipt record confirmation.
    """
    user_id = event["userId"]
    receipt_id = event["receiptId"]
    normalized = event.get("normalizedData", {})
    validation_result = event.get("validationResult", {})
    processing_status = event.get("processingStatus", "COMPLETED")

    print(f"[Save] Saving receipt {receipt_id} with status {processing_status}")

    validation_key = f"raw-extractions/{user_id}/{receipt_id}/validation.json"
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=validation_key,
        Body=json.dumps(
            {
                "validationResult": validation_result,
                "normalizedData": normalized,
                "extractedAt": event.get("extractedAt"),
                "normalizedAt": event.get("normalizedAt"),
                "validatedAt": event.get("validatedAt"),
            },
            default=str,
        ),
        ContentType="application/json",
    )

    receipt_record = {
        "userId": user_id,
        "receiptId": receipt_id,
        "processingStatus": processing_status,
        "s3ObjectKey": event["key"],
        "rawExtractionKey": event.get("rawExtractionKey"),
        "validationKey": validation_key,
        "merchantName": normalized.get("merchantName"),
        "merchantAddress": normalized.get("merchantAddress"),
        "receiptDate": normalized.get("receiptDate"),
        "receiptTime": normalized.get("receiptTime"),
        "totalAmount": normalized.get("totalAmount"),
        "subtotalAmount": normalized.get("subtotalAmount"),
        "taxAmount": normalized.get("taxAmount"),
        "tipAmount": normalized.get("tipAmount"),
        "currency": normalized.get("currency"),
        "paymentMethod": normalized.get("paymentMethod"),
        "category": normalized.get("category", "Other"),
        "receiptItems": normalized.get("receiptItems", []),
        "confidence": str(validation_result.get("confidence", 0)),
        "validationErrors": validation_result.get("errorCount", 0),
        "validationWarnings": validation_result.get("warningCount", 0),
        "extractedAt": event.get("extractedAt"),
        "normalizedAt": event.get("normalizedAt"),
        "validatedAt": event.get("validatedAt"),
        "updatedAt": now_iso(),
    }

    receipt_record = {
        k: v for k, v in receipt_record.items() if v is not None
    }

    receipt_record = sanitize_for_dynamodb(receipt_record)

    table.put_item(Item=receipt_record)

    print(
        f"[Save] Receipt {receipt_id} saved. "
        f"Status={processing_status}, "
        f"Confidence={validation_result.get('confidence')}"
    )

    return {
        "userId": user_id,
        "receiptId": receipt_id,
        "processingStatus": processing_status,
        "confidence": validation_result.get("confidence", 0),
    }
