import os
import json
import boto3
from boto3.dynamodb.conditions import Key
from botocore.config import Config

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["RECEIPTS_TABLE_NAME"])

s3_client = boto3.client(
    "s3", 
    region_name="us-east-1", 
    config=Config(signature_version="s3v4")
)

BUCKET_NAME = os.environ.get("BUCKET_NAME", "receipt-storage-bucket")

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
}

def http_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body, default=str),
    }

def get_user_id(event):
    try:
        return event["requestContext"]["authorizer"]["claims"]["sub"]
    except (KeyError, TypeError):
        return None

def generate_presigned_url(s3_key):
    """Generiši privremenu S3 URL (1 sat validnosti)."""
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=3600
        )
        return url
    except Exception as e:
        print(f"Error generating presigned URL for {s3_key}: {str(e)}")
        return None

def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return http_response(200, {"ok": True})

    user_id = get_user_id(event)
    if not user_id:
        return http_response(401, {"message": "Unauthorized"})

    try:
        result = table.query(
            KeyConditionExpression=Key("userId").eq(user_id)
        )
        receipts = result.get("Items", [])

        for receipt in receipts:
            s3_key = (
                receipt.get("s3ObjectKey") or 
                receipt.get("key") or 
                receipt.get("objectKey")
            )

            if s3_key:
                receipt["imageUrl"] = generate_presigned_url(s3_key)
            else:
                print(f"Warning: No S3 key found in receipt {receipt.get('receiptId')}")
                receipt["imageUrl"] = None

        return http_response(200, {
            "receipts": receipts,
            "count": len(receipts),
        })

    except Exception as e:
        print(f"Error fetching receipts for user {user_id}: {str(e)}")
        return http_response(500, {"message": "Internal server error"})