import os
import json
import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["RECEIPTS_TABLE_NAME"])
s3 = boto3.client("s3")
BUCKET_NAME = os.environ["BUCKET_NAME"]

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "DELETE,OPTIONS",
}

def http_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
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

        s3_key = receipt.get("s3ObjectKey")
        if s3_key:
            try:
                s3.delete_object(Bucket=BUCKET_NAME, Key=s3_key)
                print(f"Deleted S3 object: {s3_key}")
            except Exception as s3_err:
                print(f"Warning: Could not delete S3 object {s3_key}: {str(s3_err)}")

        table.delete_item(
            Key={"userId": user_id, "receiptId": receipt_id}
        )

        print(f"Deleted receipt {receipt_id} for user {user_id}")
        return http_response(200, {"message": "Receipt deleted successfully"})

    except Exception as e:
        print(f"Error deleting receipt {receipt_id}: {str(e)}")
        return http_response(500, {"message": "Internal server error"})