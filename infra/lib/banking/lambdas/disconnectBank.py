import json
import boto3

secrets = boto3.client("secretsmanager")

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}

def http_response(status_code, body):
    return {"statusCode": status_code, "headers": CORS_HEADERS, "body": json.dumps(body)}

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

    secret_name = f"plaid/access-token/{user_id}"

    try:
        secrets.delete_secret(
            SecretId=secret_name,
            ForceDeleteWithoutRecovery=True,
        )
        print(f"Deleted Plaid access token secret for user {user_id}")

        return http_response(200, {
            "message": "Bank account disconnected successfully",
        })

    except secrets.exceptions.ResourceNotFoundException:
        # Nothing was connected in the first place; treat as success
        # so the frontend can safely call this even if state is unclear.
        return http_response(200, {
            "message": "Bank account disconnected successfully",
        })

    except Exception as e:
        print(f"Error disconnecting bank for user {user_id}: {str(e)}")
        return http_response(500, {"message": "Internal server error"})