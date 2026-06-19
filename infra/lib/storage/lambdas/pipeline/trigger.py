"""
S3 trigger Lambda that starts the receipt processing Step Function.

Triggered by S3 object creation in uploads/ prefix. Parses the S3 key
to extract userId and receiptId, guards against duplicate executions using
a DynamoDB conditional write and a stable Step Functions execution name
derived from userId + receiptId + S3 ETag/versionId.
"""

import hashlib
import json
import os
import urllib.parse
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["RECEIPTS_TABLE_NAME"])
sfn_client = boto3.client("stepfunctions")

STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]

# Only retry processing if the previous attempt fully failed.
RESTARTABLE_STATUSES = {"FAILED"}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _execution_name(receipt_id: str, idempotency_token: str) -> str:
    """
    Build a stable, unique Step Functions execution name.
    SFN names must match [a-zA-Z0-9_-] and be ≤ 80 chars.
    """
    raw = f"{receipt_id}-{idempotency_token}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    safe_id = receipt_id[:36].replace(":", "-")
    return f"{safe_id}-{digest}"


def handler(event, context):
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

        print(f"[Trigger] New upload: bucket={bucket}, key={key}")

        parts = key.split("/")
        if len(parts) < 4:
            print(f"[Trigger] Invalid S3 key structure: {key}")
            continue

        user_id = parts[1]
        receipt_id = parts[2]

        # Use ETag (or versionId) to distinguish different uploads of the same receiptId.
        etag = record["s3"]["object"].get("eTag", "")
        version_id = record["s3"]["object"].get("versionId", "")
        idempotency_token = etag or version_id or "no-version"

        # Idempotency guard: only transition to PROCESSING if the record does not
        # exist yet, or if the previous run ended in FAILED (allow retry).
        try:
            table.update_item(
                Key={"userId": user_id, "receiptId": receipt_id},
                UpdateExpression=(
                    "SET #ps = :ps, #ua = :ua, #sk = :sk, #etag = :etag"
                ),
                ConditionExpression=(
                    "attribute_not_exists(#ps) OR #ps IN (:failed)"
                ),
                ExpressionAttributeNames={
                    "#ps": "processingStatus",
                    "#ua": "updatedAt",
                    "#sk": "s3ObjectKey",
                    "#etag": "s3ETag",
                },
                ExpressionAttributeValues={
                    ":ps": "PROCESSING",
                    ":ua": now_iso(),
                    ":sk": key,
                    ":etag": etag,
                    ":failed": "FAILED",
                },
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                print(
                    f"[Trigger] Receipt {receipt_id} is already in a non-restartable "
                    f"state — skipping duplicate S3 event."
                )
                continue
            raise

        sfn_input = {
            "bucket": bucket,
            "key": key,
            "userId": user_id,
            "receiptId": receipt_id,
        }

        execution_name = _execution_name(receipt_id, idempotency_token)

        try:
            response = sfn_client.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                name=execution_name,
                input=json.dumps(sfn_input),
            )
            print(
                f"[Trigger] Started execution {response['executionArn']} "
                f"for receipt {receipt_id}"
            )
        except sfn_client.exceptions.ExecutionAlreadyExists:
            print(
                f"[Trigger] Execution {execution_name} already running for "
                f"receipt {receipt_id} — skipping."
            )
