"""
Textract AnalyzeDocument fallback Lambda (repair path only).

Called when the primary Textract AnalyzeExpense extraction produced low-quality
or incomplete line-item data. Runs AnalyzeDocument with TABLES and LAYOUT
feature types to capture table cells, reading order, and nearby text that
the repair stage can use to patch ambiguous rows.

The full AnalyzeDocument response is saved to S3; only the S3 key is returned
through Step Functions.
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
    Input event: same state-machine payload produced by Validate.
    Output event: adds 'layoutKey'.
    """
    bucket = event["bucket"]
    user_id = event["userId"]
    receipt_id = event["receiptId"]

    # Use the normalised copy when available.
    source_key = event.get("normalizedInputKey") or event["key"]

    print(f"[ExtractLayout] Running AnalyzeDocument (TABLES, LAYOUT) on {source_key}")

    response = textract_client.analyze_document(
        Document={
            "S3Object": {
                "Bucket": bucket,
                "Name": source_key,
            }
        },
        FeatureTypes=["TABLES", "LAYOUT"],
    )

    response.pop("ResponseMetadata", None)

    block_count = len(response.get("Blocks", []))
    layout_key = f"raw-extractions/{user_id}/{receipt_id}/layout.json"

    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=layout_key,
        Body=json.dumps(response, default=str),
        ContentType="application/json",
    )

    print(f"[ExtractLayout] blocks={block_count}, saved to {layout_key}")

    return {
        **event,
        "layoutKey": layout_key,
        "layoutExtractedAt": now_iso(),
    }
