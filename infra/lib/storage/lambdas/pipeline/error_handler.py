"""
Error handler for the receipt processing pipeline.

Called when any stage in the Step Functions state machine fails.
Marks the receipt as FAILED and stores the error details.
"""

import os
import json
import boto3
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["RECEIPTS_TABLE_NAME"])


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def handler(event, context):
    """
    Input event (from Step Functions Catch):
    {
        "userId": "...",
        "receiptId": "...",
        "error": { "Error": "...", "Cause": "..." }
    }
    """
    user_id = event.get("userId")
    receipt_id = event.get("receiptId")
    error_info = event.get("error", {})

    error_type = error_info.get("Error", "Unknown")
    error_cause = error_info.get("Cause", "Unknown error occurred")

    try:
        cause_data = json.loads(error_cause)
        error_message = cause_data.get("errorMessage", error_cause)
    except (json.JSONDecodeError, TypeError):
        error_message = str(error_cause)

    failed_stage = event.get("failedStage", "Unknown")

    print(
        f"[ErrorHandler] Receipt {receipt_id} failed at stage '{failed_stage}'. "
        f"Error: {error_type} - {error_message[:500]}"
    )

    if user_id and receipt_id:
        table.update_item(
            Key={"userId": user_id, "receiptId": receipt_id},
            UpdateExpression=(
                "SET #ps = :ps, #ua = :ua, #em = :em, #fs = :fs"
            ),
            ExpressionAttributeNames={
                "#ps": "processingStatus",
                "#ua": "updatedAt",
                "#em": "errorMessage",
                "#fs": "failedStage",
            },
            ExpressionAttributeValues={
                ":ps": "FAILED",
                ":ua": now_iso(),
                ":em": error_message[:1000],
                ":fs": failed_stage,
            },
        )

    return {
        "userId": user_id,
        "receiptId": receipt_id,
        "processingStatus": "FAILED",
        "failedStage": failed_stage,
        "errorMessage": error_message[:500],
    }
