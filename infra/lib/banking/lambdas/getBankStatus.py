import json
import boto3

secrets = boto3.client("secretsmanager")

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
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

    # The user is "registered" if either their own Plaid credentials
    # (client_id + secret) or a directly-registered access token exist. We only
    # describe the secrets so the stored values never enter this response.
    for secret_name in (
        f"plaid/credentials/{user_id}",
        f"plaid/access-token/{user_id}",
    ):
        try:
            secrets.describe_secret(SecretId=secret_name)
            return http_response(200, {"connected": True})
        except secrets.exceptions.ResourceNotFoundException:
            continue
        except Exception as e:
            print(f"Error checking bank status for user {user_id}: {str(e)}")
            return http_response(500, {"message": "Internal server error"})

    return http_response(200, {"connected": False})