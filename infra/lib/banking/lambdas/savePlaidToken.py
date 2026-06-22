"""
Save (or replace) a user's Plaid API access token.

The token is stored *only* in AWS Secrets Manager under
``plaid/access-token/{userId}`` — never in DynamoDB and never returned to the
frontend. Callers may overwrite the token at any time by POSTing a new value;
deletion is handled by the existing disconnectBank Lambda, and registration
status is reported (without ever exposing the token) by getBankStatus.
"""

import json
import boto3
from datetime import datetime, timezone

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


def extract_token(event):
    """Pull the access token out of the request body, tolerating field aliases."""
    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(body, dict):
        return None

    for field in ("accessToken", "token", "plaidToken", "apiToken"):
        value = body.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return http_response(200, {"ok": True})

    user_id = get_user_id(event)
    if not user_id:
        return http_response(401, {"message": "Unauthorized"})

    token = extract_token(event)
    if not token:
        return http_response(400, {"message": "Missing Plaid access token"})

    secret_name = f"plaid/access-token/{user_id}"
    secret_string = json.dumps({
        "accessToken": token,
        "source": "manual",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    })

    try:
        try:
            secrets.create_secret(Name=secret_name, SecretString=secret_string)
        except secrets.exceptions.ResourceExistsException:
            secrets.update_secret(SecretId=secret_name, SecretString=secret_string)

        # Never echo the token back — only confirm it is registered.
        return http_response(200, {"message": "Plaid token saved", "registered": True})

    except Exception as e:
        print(f"Error saving Plaid token for user {user_id}: {str(e)}")
        return http_response(500, {"message": "Internal server error"})
