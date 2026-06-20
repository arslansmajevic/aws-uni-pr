"""
Upload Lambda for multi-image single-receipt.

Accepts multiple images in one request and ties them all to a single receiptId.
Writes a PROCESSING status to DynamoDB before uploading to S3 so the S3-event
trigger (trigger.py) skips the individual uploads and doesn't start duplicate
Step Functions executions. The pipeline is started directly from here with the
full list of image keys so every image is processed together.
"""

import base64
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
sfn_client = boto3.client("stepfunctions")

BUCKET_NAME = os.environ["BUCKET_NAME"]
RECEIPTS_TABLE_NAME = os.environ["RECEIPTS_TABLE_NAME"]
STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]

table = dynamodb.Table(RECEIPTS_TABLE_NAME)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}

# Hard cap: Textract AnalyzeExpense supports up to 15 pages for PDFs; we keep a
# reasonable bound per receipt to avoid runaway costs.
MAX_IMAGES = 10


def http_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
    }


def sanitize_filename(filename):
    filename = filename.strip()
    filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
    return filename or "image"


def get_user_id(event):
    try:
        claims = event["requestContext"]["authorizer"]["claims"]
        return claims["sub"]
    except (KeyError, TypeError):
        return None


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _execution_name(receipt_id: str, token: str) -> str:
    """Build a stable, unique Step Functions execution name (≤ 80 chars)."""
    raw = f"{receipt_id}-{token}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    safe_id = receipt_id[:36].replace(":", "-")
    return f"{safe_id}-{digest}"


def handler(event, context):
    try:
        if event.get("httpMethod") == "OPTIONS":
            return http_response(200, {"ok": True})

        user_id = get_user_id(event)
        if not user_id:
            return http_response(401, {"message": "Unauthorized - missing user identity"})

        body = event.get("body")
        if not body:
            return http_response(400, {"message": "Missing request body"})

        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode("utf-8")

        payload = json.loads(body)
        images = payload.get("images")

        if not images:
            return http_response(400, {"message": "Missing 'images' array"})
        if not isinstance(images, list):
            return http_response(400, {"message": "'images' must be an array"})
        if len(images) < 2:
            return http_response(
                400,
                {"message": "Use the single-image endpoint for one image. "
                 "Provide at least 2 images for this endpoint."},
            )
        if len(images) > MAX_IMAGES:
            return http_response(
                400,
                {"message": f"Too many images. Maximum {MAX_IMAGES} per receipt."},
            )

        receipt_id = str(uuid.uuid4())

        # --- Write PROCESSING status to DynamoDB BEFORE uploading to S3 ---
        # This ensures the S3-event trigger (trigger.py) sees PROCESSING and
        # skips starting a duplicate execution for each individual image.
        try:
            table.update_item(
                Key={"userId": user_id, "receiptId": receipt_id},
                UpdateExpression="SET #ps = :ps, #ua = :ua",
                ConditionExpression="attribute_not_exists(#ps)",
                ExpressionAttributeNames={
                    "#ps": "processingStatus",
                    "#ua": "updatedAt",
                },
                ExpressionAttributeValues={
                    ":ps": "PROCESSING",
                    ":ua": now_iso(),
                },
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return http_response(409, {"message": "Receipt ID collision — please retry."})
            raise

        # --- Upload all images to S3 ---
        keys = []
        for i, img in enumerate(images):
            file_name = img.get("fileName")
            content_type = img.get("contentType", "application/octet-stream")
            image_base64 = img.get("imageBase64")

            if not file_name:
                return http_response(400, {"message": f"Missing fileName for image {i}"})
            if not image_base64:
                return http_response(400, {"message": f"Missing imageBase64 for image {i}"})

            image_bytes = base64.b64decode(image_base64)
            safe_name = sanitize_filename(file_name)
            object_key = f"uploads/{user_id}/{receipt_id}/{safe_name}"

            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=object_key,
                Body=image_bytes,
                ContentType=content_type,
            )
            keys.append(object_key)

        print(
            f"[UploadMulti] Uploaded {len(keys)} images for receipt {receipt_id}: {keys}"
        )

        # --- Start Step Functions with all keys ---
        sfn_input = {
            "bucket": BUCKET_NAME,
            "key": keys[0],   # primary key kept for backward compatibility
            "keys": keys,     # full list consumed by preflight / textract stages
            "userId": user_id,
            "receiptId": receipt_id,
        }

        execution_name = _execution_name(receipt_id, "multi")

        try:
            response = sfn_client.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                name=execution_name,
                input=json.dumps(sfn_input),
            )
            print(
                f"[UploadMulti] Started execution {response['executionArn']} "
                f"for receipt {receipt_id}"
            )
        except sfn_client.exceptions.ExecutionAlreadyExists:
            print(
                f"[UploadMulti] Execution {execution_name} already exists "
                f"for receipt {receipt_id} — skipping duplicate start."
            )

        return http_response(201, {
            "message": f"Successfully queued {len(keys)} images for processing",
            "receiptId": receipt_id,
            "keys": keys,
        })

    except json.JSONDecodeError:
        return http_response(400, {"message": "Invalid JSON body"})
    except base64.binascii.Error:
        return http_response(400, {"message": "Invalid base64 image data"})
    except Exception as error:
        print(f"[UploadMulti] Unexpected error: {error}")
        return http_response(500, {"message": "Internal server error"})
