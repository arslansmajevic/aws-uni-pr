"""
Stage 1: Extract receipt data using Textract AnalyzeExpense.

Calls synchronous Textract AnalyzeExpense on the normalized receipt image or
document. Saves the complete raw Textract response to S3 and returns only
small metadata through Step Functions to avoid hitting the 256 KB payload limit.
"""

import json
import os
from datetime import datetime, timezone

import boto3

s3_client = boto3.client("s3")
textract_client = boto3.client("textract")

BUCKET_NAME = os.environ["BUCKET_NAME"]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def handler(event, context):
    """
    Input event:
    {
      "bucket":             "...",
      "key":                "uploads/<userId>/<receiptId>/<filename>",
      "normalizedInputKey": "normalized-inputs/<userId>/<receiptId>/receipt.<ext>",
      "userId":             "...",
      "receiptId":          "..."
    }

    Output event (adds):
    {
      "textractKey":          "raw-extractions/<userId>/<receiptId>/textract.json",
      "extractedAt":          "<ISO timestamp>",
      "extractionProvider":   "TEXTRACT_ANALYZE_EXPENSE"
    }

    The full Textract JSON is stored in S3 — NOT returned through Step Functions.
    """
    bucket = event["bucket"]
    user_id = event["userId"]
    receipt_id = event["receiptId"]

    # Prefer the normalizedInputKey (validated copy); fall back to the original.
    source_key = event.get("normalizedInputKey") or event["key"]

    print(f"[ExtractTextract] Running AnalyzeExpense on s3://{bucket}/{source_key}")

    response = textract_client.analyze_expense(
        Document={
            "S3Object": {
                "Bucket": bucket,
                "Name": source_key,
            }
        }
    )

    # Drop the ResponseMetadata before saving — it adds noise and varies per call.
    response.pop("ResponseMetadata", None)

    textract_key = f"raw-extractions/{user_id}/{receipt_id}/textract.json"

    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=textract_key,
        Body=json.dumps(response, default=str),
        ContentType="application/json",
    )

    doc_count = len(response.get("ExpenseDocuments", []))
    print(
        f"[ExtractTextract] Extraction complete. "
        f"documents={doc_count}, saved to {textract_key}"
    )

    return {
        **event,
        "textractKey": textract_key,
        "extractedAt": now_iso(),
        "extractionProvider": "TEXTRACT_ANALYZE_EXPENSE",
    }
