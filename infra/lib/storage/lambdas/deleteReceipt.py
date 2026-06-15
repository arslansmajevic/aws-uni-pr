import os
import json
import boto3

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

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

    try:
        user_id = get_user_id(event)
        if not user_id:
            return http_response(401, {"message": "Unauthorized"})

        table_name = os.environ.get("RECEIPTS_TABLE_NAME")
        bucket_name = os.environ.get("BUCKET_NAME")
        
        if not table_name or not bucket_name:
            return http_response(500, {
                "message": "Internal configuration error: Missing required environment variables on AWS Lambda stack binding."
            })

        table = dynamodb.Table(table_name)

        receipt_id = (event.get("pathParameters") or {}).get("receiptId")
        if not receipt_id:
            return http_response(400, {"message": "Missing required path parameter: receiptId"})

        result = table.get_item(
            Key={"userId": user_id, "receiptId": receipt_id}
        )
        receipt = result.get("Item")

        if not receipt:
            return http_response(404, {"message": "Receipt record target entry not found inside DB catalog."})

        s3_key = receipt.get("s3ObjectKey")
        if s3_key:
            try:
                s3.delete_object(Bucket=bucket_name, Key=s3_key)
                print(f"Successfully purged target source binary file from S3 bucket: {s3_key}")
            except Exception as s3_err:
                print(f"Warning: Non-blocking error encountered during S3 object target drop for {s3_key}: {str(s3_err)}")

        table.delete_item(
            Key={"userId": user_id, "receiptId": receipt_id}
        )

        print(f"Successfully deleted database index tracking token metadata entry {receipt_id} for user {user_id}")
        return http_response(200, {"message": "Receipt tracking index entries cleanly expunged from the ecosystem successfully."})

    except Exception as e:
        print(f"Unhandled critical execution architecture crash captured inside handler engine: {str(e)}")
        return http_response(500, {"message": f"Internal server error context: {str(e)}"})