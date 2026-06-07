import os
import json
import boto3

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

    receipt_id = (event.get("pathParameters") or {}).get("receiptId")
    if not receipt_id:
        return http_response(400, {"message": "Missing receiptId"})

    try:
        result = table.get_item(
            Key={"userId": user_id, "receiptId": receipt_id}
        )

        receipt = result.get("Item")

        if not receipt:
            return http_response(404, {"message": "Receipt not found"})

        return http_response(200, {"receipt": receipt})

    except Exception as e:
        print(f"Error fetching receipt {receipt_id}: {str(e)}")
        return http_response(500, {"message": "Internal server error"})