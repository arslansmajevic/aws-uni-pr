"""
S3 trigger Lambda that starts the receipt processing Step Function.

Triggered by S3 object creation in uploads/ prefix. Parses the S3 key
to extract userId and receiptId, marks the receipt as PROCESSING,
then starts the Step Functions state machine.
"""

import os
import json
import boto3
import urllib.parse
from datetime import datetime, timezone

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["RECEIPTS_TABLE_NAME"])
sfn_client = boto3.client("stepfunctions")

STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


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

        table.update_item(
            Key={"userId": user_id, "receiptId": receipt_id},
            UpdateExpression="SET #ps = :ps, #ua = :ua, #sk = :sk",
            ExpressionAttributeNames={
                "#ps": "processingStatus",
                "#ua": "updatedAt",
                "#sk": "s3ObjectKey",
            },
            ExpressionAttributeValues={
                ":ps": "PROCESSING",
                ":ua": now_iso(),
                ":sk": key,
            },
        )

        sfn_input = {
            "bucket": bucket,
            "key": key,
            "userId": user_id,
            "receiptId": receipt_id,
        }

        execution_name = f"{receipt_id[:36]}-{int(datetime.now(timezone.utc).timestamp())}"

        response = sfn_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=execution_name,
            input=json.dumps(sfn_input),
        )

        print(
            f"[Trigger] Started execution {response['executionArn']} "
            f"for receipt {receipt_id}"
        )
