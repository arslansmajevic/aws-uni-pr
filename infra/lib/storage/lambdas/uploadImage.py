import base64
import json
import os
import re
import uuid
import boto3

s3 = boto3.client("s3")

BUCKET_NAME = os.environ["BUCKET_NAME"]


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
        },
        "body": json.dumps(body),
    }


def sanitize_filename(filename):
    filename = filename.strip()
    filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
    return filename or "image"


def handler(event, context):
    try:
        if event.get("httpMethod") == "OPTIONS":
            return response(200, {"ok": True})

        body = event.get("body")

        if not body:
            return response(400, {"message": "Missing request body"})

        if event.get("isBase64Encoded"):
            body = base64.b64decode(body).decode("utf-8")

        payload = json.loads(body)

        file_name = payload.get("fileName")
        content_type = payload.get("contentType", "application/octet-stream")
        image_base64 = payload.get("imageBase64")

        if not file_name:
            return response(400, {"message": "Missing fileName"})

        if not image_base64:
            return response(400, {"message": "Missing imageBase64"})

        image_bytes = base64.b64decode(image_base64)

        safe_file_name = sanitize_filename(file_name)
        object_key = f"uploads/{uuid.uuid4()}-{safe_file_name}"

        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=object_key,
            Body=image_bytes,
            ContentType=content_type,
        )

        return response(
            201,
            {
                "message": "Image uploaded successfully",
                "bucket": BUCKET_NAME,
                "key": object_key,
            },
        )

    except json.JSONDecodeError:
        return response(400, {"message": "Invalid JSON body"})

    except base64.binascii.Error:
        return response(400, {"message": "Invalid base64 image"})

    except Exception as error:
        print(error)
        return response(500, {"message": "Internal server error"})