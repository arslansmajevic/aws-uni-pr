"""
Stage 1: OCR Extraction using AWS Textract AnalyzeExpense.

Reads the receipt image from S3, runs Textract AnalyzeExpense,
stores the raw extraction JSON in S3, and passes it downstream.
"""

import os
import json
import boto3
from datetime import datetime, timezone

s3_client = boto3.client("s3")
textract_client = boto3.client("textract")

BUCKET_NAME = os.environ["BUCKET_NAME"]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def handler(event, context):
    """
    Input event:
    {
        "bucket": "...",
        "key": "uploads/<userId>/<receiptId>/<filename>",
        "userId": "...",
        "receiptId": "..."
    }

    Output:
    {
        ...input fields,
        "rawExtractionKey": "raw-extractions/<userId>/<receiptId>/textract.json",
        "extractedAt": "ISO timestamp",
        "textractResult": { ... raw Textract response ... }
    }
    """
    bucket = event["bucket"]
    key = event["key"]
    user_id = event["userId"]
    receipt_id = event["receiptId"]

    print(f"[Extract] Starting OCR for {key}")

    textract_response = textract_client.analyze_expense(
        Document={
            "S3Object": {
                "Bucket": bucket,
                "Name": key,
            }
        }
    )

    raw_extraction_key = f"raw-extractions/{user_id}/{receipt_id}/textract.json"

    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=raw_extraction_key,
        Body=json.dumps(textract_response, default=str),
        ContentType="application/json",
    )

    print(
        f"[Extract] Textract completed. "
        f"ExpenseDocuments={len(textract_response.get('ExpenseDocuments', []))}. "
        f"Raw saved to {raw_extraction_key}"
    )

    return {
        **event,
        "rawExtractionKey": raw_extraction_key,
        "extractedAt": now_iso(),
        "textractResult": textract_response,
    }
