"""
Error handler for the receipt processing pipeline.

Called when any stage in the Step Functions state machine raises an
unhandled exception.

Distinguishes between:
  FAILED      — infrastructure failure, invalid document, unsupported format,
                irrecoverable AWS service error.
  NEEDS_REVIEW — extraction completed but the result is unreliable. This is
                NOT routed here; the Validate Lambda sets it directly.

Stores the failed stage, sanitized error message, error type, and timestamp.
Does not expose raw stack traces or internal service details to clients.
"""

import json
import os
from datetime import datetime, timezone

import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["RECEIPTS_TABLE_NAME"])

# Infrastructure/service error substrings that map to specific FAILED reasons.
_INFRA_PATTERNS = {
    "SubscriptionRequiredException": "Service subscription required",
    "AccessDeniedException": "Insufficient IAM permissions",
    "InvalidS3ObjectException": "S3 object not accessible",
    "UnsupportedDocumentException": "Document format not supported by Textract",
    "DocumentTooLargeException": "Document exceeds size limit",
    "BadDocumentException": "Document is corrupt or unreadable",
    "ProvisionedThroughputExceededException": "DynamoDB throughput exceeded",
    "ThrottlingException": "Request throttled by AWS service",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _sanitize_error(raw: str, max_len: int = 500) -> str:
    """Return a client-safe error message, stripping internal details."""
    if not raw:
        return "Unknown error"
    # Truncate and strip any Python traceback noise.
    msg = raw[:max_len]
    # Remove stack trace lines.
    lines = [ln for ln in msg.splitlines() if not ln.strip().startswith("File ")]
    return " ".join(lines).strip() or "Processing failed"


def _classify_error(error_type: str, error_message: str) -> str:
    """Return a brief human-readable failure reason."""
    for pattern, reason in _INFRA_PATTERNS.items():
        if pattern in error_type or pattern in error_message:
            return reason
    return "Unexpected processing error"


def handler(event, context):
    """
    Input event (from Step Functions Catch):
    {
      "userId":      "...",
      "receiptId":   "...",
      "failedStage": "...",
      "error": {
        "Error": "...",
        "Cause": "..."
      }
    }
    """
    user_id = event.get("userId")
    receipt_id = event.get("receiptId")
    error_info = event.get("error", {})
    failed_stage = event.get("failedStage", "Unknown")

    error_type = error_info.get("Error", "Unknown")
    raw_cause = error_info.get("Cause", "")

    # Cause may be a JSON string with errorMessage / errorType.
    error_message = raw_cause
    try:
        cause_data = json.loads(raw_cause)
        error_message = cause_data.get("errorMessage", raw_cause)
        if not error_type or error_type == "Unknown":
            error_type = cause_data.get("errorType", error_type)
    except (json.JSONDecodeError, TypeError):
        pass

    sanitized_message = _sanitize_error(str(error_message))
    failure_reason = _classify_error(error_type, str(error_message))

    print(
        f"[ErrorHandler] Receipt {receipt_id} FAILED at '{failed_stage}'. "
        f"errorType={error_type}, reason={failure_reason}"
    )

    if user_id and receipt_id:
        table.update_item(
            Key={"userId": user_id, "receiptId": receipt_id},
            UpdateExpression=(
                "SET #ps = :ps, #ua = :ua, #em = :em, "
                "#fs = :fs, #et = :et, #fr = :fr"
            ),
            ExpressionAttributeNames={
                "#ps": "processingStatus",
                "#ua": "updatedAt",
                "#em": "errorMessage",
                "#fs": "failedStage",
                "#et": "errorType",
                "#fr": "failureReason",
            },
            ExpressionAttributeValues={
                ":ps": "FAILED",
                ":ua": now_iso(),
                ":em": sanitized_message,
                ":fs": failed_stage,
                ":et": error_type,
                ":fr": failure_reason,
            },
        )

    return {
        "userId": user_id,
        "receiptId": receipt_id,
        "processingStatus": "FAILED",
        "failedStage": failed_stage,
        "failureReason": failure_reason,
    }

