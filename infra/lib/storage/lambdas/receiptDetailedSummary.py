import json
import os

import boto3
from boto3.dynamodb.conditions import Key
from botocore.config import Config


dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["RECEIPTS_TABLE_NAME"])

s3_client = boto3.client(
    "s3",
    region_name=os.environ.get("AWS_REGION", "eu-central-1"),
    config=Config(signature_version="s3v4"),
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
    try:
        return s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": s3_key},
            ExpiresIn=3600,
        )
    except Exception as error:
        print(f"Failed to generate presigned URL for {s3_key}: {str(error)}")
        return None


def normalize_receipt_items(receipt):
    items = receipt.get("receiptItems") or receipt.get("lineItems") or []

    if not isinstance(items, list):
        return []

    normalized_items = []

    for item in items:
        if not isinstance(item, dict):
            continue

        normalized_items.append(
            {
                "name": item.get("name") or item.get("description") or "Item",
                "quantity": item.get("quantity") or "1",
                "price": item.get("price") or receipt.get("totalAmount") or "0",
            }
        )

    if not normalized_items and receipt.get("totalAmount"):
        normalized_items.append(
            {
                "name": receipt.get("merchantName") or "Receipt total",
                "quantity": "1",
                "price": receipt.get("totalAmount"),
            }
        )

    return normalized_items


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return http_response(200, {"ok": True})

    user_id = get_user_id(event)
    if not user_id:
        return http_response(401, {"message": "Unauthorized"})

    receipt_id = (event.get("pathParameters") or {}).get("receiptId")
    if not receipt_id:
        return http_response(400, {"message": "Missing required path parameter: receiptId"})

    try:
        result = table.get_item(
            Key={"userId": user_id, "receiptId": receipt_id}
        )
        receipt = result.get("Item")

        if not receipt:
            return http_response(404, {"message": "Receipt not found"})

        s3_key = receipt.get("s3ObjectKey") or receipt.get("key") or receipt.get("objectKey")

        response_body = {
            "receiptId": receipt.get("receiptId", receipt_id),
            "merchantName": receipt.get("merchantName"),
            "receiptDate": receipt.get("receiptDate"),
            "receiptTime": receipt.get("receiptTime"),
            "category": receipt.get("category"),
            "totalAmount": receipt.get("totalAmount"),
            "currency": receipt.get("currency") or "USD",
            "transactionMatchStatus": receipt.get("transactionMatchStatus"),
            "matchedTransactionName": receipt.get("matchedTransactionName"),
            "matchedTransactionId": receipt.get("matchedTransactionId"),
            "matchedAmount": receipt.get("matchedAmount"),
            "matchedDate": receipt.get("matchedDate"),
            "receiptItems": normalize_receipt_items(receipt),
            "imageUrl": generate_presigned_url(s3_key) if s3_key else None,
        }

        return http_response(200, response_body)
    except Exception as error:
        print(f"Error loading receipt summary for user {user_id} and receipt {receipt_id}: {str(error)}")
        return http_response(500, {"message": "Internal server error"})