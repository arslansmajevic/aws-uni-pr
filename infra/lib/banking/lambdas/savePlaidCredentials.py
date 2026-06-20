"""
Save (or replace) a user's own Plaid API credentials (client_id + secret).

In the sandbox flow the user supplies their personal Plaid ``client_id`` and
``secret``. These are stored *only* in AWS Secrets Manager under
``plaid/credentials/{userId}`` — never in DynamoDB and never returned to the
frontend. At receipt-matching time the pipeline uses these credentials to mint
a public token, exchange it for an access token, and query transactions.

Callers may overwrite the credentials at any time by POSTing new values;
deletion is handled by the existing disconnectBank Lambda, and registration
status is reported (without ever exposing the values) by getBankStatus.
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


def _first_string(body, fields):
    for field in fields:
        value = body.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def extract_credentials(event):
    """Pull the client_id + secret out of the request body, tolerating aliases.

    Returns ``(client_id, secret, env)`` where any missing value is ``None``.
    """
    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return None, None, None

    if not isinstance(body, dict):
        return None, None, None

    client_id = _first_string(body, ("clientId", "client_id", "plaidClientId"))
    secret = _first_string(body, ("secret", "plaidSecret", "clientSecret"))
    env = _first_string(body, ("env", "environment")) or "sandbox"
    return client_id, secret, env


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return http_response(200, {"ok": True})

    user_id = get_user_id(event)
    if not user_id:
        return http_response(401, {"message": "Unauthorized"})

    client_id, secret, env = extract_credentials(event)
    if not client_id or not secret:
        return http_response(400, {"message": "Missing Plaid client_id or secret"})

    secret_name = f"plaid/credentials/{user_id}"
    secret_string = json.dumps({
        "clientId": client_id,
        "secret": secret,
        "env": env,
        "source": "manual",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    })

    try:
        try:
            secrets.create_secret(Name=secret_name, SecretString=secret_string)
        except secrets.exceptions.ResourceExistsException:
            secrets.update_secret(SecretId=secret_name, SecretString=secret_string)

        # Never echo the credentials back — only confirm they are registered.
        return http_response(200, {"message": "Plaid credentials saved", "registered": True})

    except Exception as e:
        print(f"Error saving Plaid credentials for user {user_id}: {str(e)}")
        return http_response(500, {"message": "Internal server error"})
