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


def _analyze_expense(bucket: str, key: str) -> list:
    """
    Call Textract AnalyzeExpense on a single S3 object and return the
    ExpenseDocuments list (ResponseMetadata stripped).
    """
    print(f"[ExtractTextract] AnalyzeExpense on s3://{bucket}/{key}")
    response = textract_client.analyze_expense(
        Document={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    response.pop("ResponseMetadata", None)
    return response.get("ExpenseDocuments", [])


def handler(event, context):
    """
    Input event (single image):
    {
      "bucket":             "...",
      "key":                "uploads/<userId>/<receiptId>/<filename>",
      "normalizedInputKey": "normalized-inputs/<userId>/<receiptId>/receipt-0.jpg",
      "userId":             "...",
      "receiptId":          "..."
    }

    Input event (multi-image):
    {
      "bucket":              "...",
      "key":                 "uploads/.../image-0.jpg",
      "normalizedInputKeys": ["normalized-inputs/.../receipt-0.jpg",
                               "normalized-inputs/.../receipt-1.jpg"],
      "userId":              "...",
      "receiptId":           "..."
    }

    Output event adds:
    {
      "textractKey":        "raw-extractions/<userId>/<receiptId>/textract.json",
      "extractedAt":        "<ISO timestamp>",
      "extractionProvider": "TEXTRACT_ANALYZE_EXPENSE"
    }

    When multiple images are supplied all their ExpenseDocuments are merged into
    a single JSON so the downstream normalize stage works unchanged.
    """
    bucket = event["bucket"]
    user_id = event["userId"]
    receipt_id = event["receiptId"]

    # Multi-image path takes precedence; fall back to single normalizedInputKey.
    normalized_keys = event.get("normalizedInputKeys") or [
        event.get("normalizedInputKey") or event["key"]
    ]

    all_expense_docs = []
    for nk in normalized_keys:
        docs = _analyze_expense(bucket, nk)
        all_expense_docs.extend(docs)

    merged = {"ExpenseDocuments": all_expense_docs}

    textract_key = f"raw-extractions/{user_id}/{receipt_id}/textract.json"

    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=textract_key,
        Body=json.dumps(merged, default=str),
        ContentType="application/json",
    )

    print(
        f"[ExtractTextract] Extraction complete. "
        f"images={len(normalized_keys)}, documents={len(all_expense_docs)}, "
        f"saved to {textract_key}"
    )

    return {
        **event,
        "textractKey": textract_key,
        "extractedAt": now_iso(),
        "extractionProvider": "TEXTRACT_ANALYZE_EXPENSE",
    }
