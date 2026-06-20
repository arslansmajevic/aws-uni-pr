"""
Add-image Lambda: append another image to an existing receipt and reprocess.

Accepts a single image for an existing receiptId, uploads it alongside the
images already stored for that receipt, and restarts the Step Functions
pipeline with the *full* set of image keys so every page is processed together
for the best possible extraction.

Mirrors uploadMultiImage.py: it writes a PROCESSING status to DynamoDB before
uploading to S3 so the S3-event trigger (trigger.py) skips starting a
duplicate execution, then starts the pipeline directly with all image keys.
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

# Keep the same per-receipt bound as the multi-image upload endpoint.
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
    """Build a stable, unique Step Functions execution name (<= 80 chars)."""
    raw = f"{receipt_id}-{token}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    safe_id = receipt_id[:36].replace(":", "-")
    return f"{safe_id}-{digest}"


def _existing_image_keys(receipt):
    """Ordered, de-duplicated list of keys already stored for the receipt."""
    primary_key = (
        receipt.get("s3ObjectKey") or receipt.get("key") or receipt.get("objectKey")
    )
    image_keys = receipt.get("imageKeys")
    if not isinstance(image_keys, list):
        image_keys = []

    ordered = []
    for key in [primary_key, *image_keys]:
        if key and key not in ordered:
            ordered.append(key)
    return ordered


def handler(event, context):
    try:
        if event.get("httpMethod") == "OPTIONS":
            return http_response(200, {"ok": True})

        user_id = get_user_id(event)
        if not user_id:
            return http_response(401, {"message": "Unauthorized - missing user identity"})

        receipt_id = (event.get("pathParameters") or {}).get("receiptId")
        if not receipt_id:
            return http_response(400, {"message": "Missing required path parameter: receiptId"})

        body = event.get("body")
        if not body:
            return http_response(400, {"message": "Missing request body"})

        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode("utf-8")

        payload = json.loads(body)
        file_name = payload.get("fileName")
        content_type = payload.get("contentType", "application/octet-stream")
        image_base64 = payload.get("imageBase64")

        if not file_name:
            return http_response(400, {"message": "Missing fileName"})
        if not image_base64:
            return http_response(400, {"message": "Missing imageBase64"})

        # --- Verify the receipt exists and belongs to the caller ---
        result = table.get_item(Key={"userId": user_id, "receiptId": receipt_id})
        receipt = result.get("Item")
        if not receipt:
            return http_response(404, {"message": "Receipt not found"})

        existing_keys = _existing_image_keys(receipt)
        if len(existing_keys) >= MAX_IMAGES:
            return http_response(
                400,
                {"message": f"Too many images. Maximum {MAX_IMAGES} per receipt."},
            )

        # --- Mark the receipt as PROCESSING before the S3 upload ---
        # This makes the S3-event trigger (trigger.py) skip starting a
        # duplicate single-image execution for the new object.
        table.update_item(
            Key={"userId": user_id, "receiptId": receipt_id},
            UpdateExpression="SET #ps = :ps, #ua = :ua",
            ExpressionAttributeNames={
                "#ps": "processingStatus",
                "#ua": "updatedAt",
            },
            ExpressionAttributeValues={
                ":ps": "PROCESSING",
                ":ua": now_iso(),
            },
        )

        # --- Upload the new image to S3 ---
        image_bytes = base64.b64decode(image_base64)
        safe_name = sanitize_filename(file_name)
        # Prefix with a short token so a repeated filename never overwrites an
        # image that already belongs to this receipt.
        unique_name = f"{uuid.uuid4().hex[:8]}-{safe_name}"
        object_key = f"uploads/{user_id}/{receipt_id}/{unique_name}"

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=object_key,
            Body=image_bytes,
            ContentType=content_type,
        )

        # --- Reprocess the receipt with every image (old + new) ---
        keys = [*existing_keys, object_key]

        print(
            f"[AddImage] Added image to receipt {receipt_id}; reprocessing "
            f"{len(keys)} image(s): {keys}"
        )

        sfn_input = {
            "bucket": BUCKET_NAME,
            "key": keys[0],   # primary key kept for backward compatibility
            "keys": keys,     # full list consumed by preflight / textract stages
            "userId": user_id,
            "receiptId": receipt_id,
        }

        # Token derived from the new key so every add starts a fresh execution
        # without colliding with the receipt's previous run names.
        execution_name = _execution_name(receipt_id, object_key)

        try:
            response = sfn_client.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                name=execution_name,
                input=json.dumps(sfn_input),
            )
            print(
                f"[AddImage] Started execution {response['executionArn']} "
                f"for receipt {receipt_id}"
            )
        except sfn_client.exceptions.ExecutionAlreadyExists:
            print(
                f"[AddImage] Execution {execution_name} already exists "
                f"for receipt {receipt_id} - skipping duplicate start."
            )

        return http_response(201, {
            "message": f"Image added; reprocessing {len(keys)} images",
            "receiptId": receipt_id,
            "key": object_key,
            "keys": keys,
        })

    except json.JSONDecodeError:
        return http_response(400, {"message": "Invalid JSON body"})
    except base64.binascii.Error:
        return http_response(400, {"message": "Invalid base64 image data"})
    except ClientError as error:
        print(f"[AddImage] AWS error: {error}")
        return http_response(500, {"message": "Internal server error"})
    except Exception as error:
        print(f"[AddImage] Unexpected error: {error}")
        return http_response(500, {"message": "Internal server error"})
