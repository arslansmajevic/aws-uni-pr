import os
import json
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["RECEIPTS_TABLE_NAME"])

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

        return http_response(200, {
            "receipts": receipts,
            "count": len(receipts),
        })

    except Exception as e:
        print(f"Error fetching receipts for user {user_id}: {str(e)}")
        return http_response(500, {"message": "Internal server error"})