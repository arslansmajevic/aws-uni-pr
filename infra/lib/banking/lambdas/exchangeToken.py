import json
import boto3
import urllib.request
import time
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

def get_plaid_creds():
    secret = secrets.get_secret_value(SecretId="plaid/credentials")
    return json.loads(secret["SecretString"])

PLAID_URLS = {
    "sandbox": "https://sandbox.plaid.com",
    "production": "https://production.plaid.com",
}

def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return http_response(200, {"ok": True})

    user_id = get_user_id(event)
    if not user_id:
        return http_response(401, {"message": "Unauthorized"})

    try:
        body = json.loads(event.get("body", "{}"))
        public_token = body.get("publicToken")
        if not public_token:
            return http_response(400, {"message": "Missing publicToken"})

        creds = get_plaid_creds()
        base_url = PLAID_URLS.get(creds["env"], PLAID_URLS["sandbox"])

        payload = json.dumps({
            "client_id": creds["clientId"],
            "secret": creds["secret"],
            "public_token": public_token,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{base_url}/item/public_token/exchange",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    result = json.loads(resp.read())
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:  
                    wait = 2 ** attempt  
                    print(f"Rate limited, waiting {wait}s (attempt {attempt+1})")
                    time.sleep(wait)
                    if attempt == max_retries - 1:
                        return http_response(429, {"message": "Bank API rate limit exceeded, try again later"})
                elif e.code in (400, 401):
                    error_body = json.loads(e.read())
                    plaid_error = error_body.get("error_code", "UNKNOWN")
                    print(f"Plaid error: {plaid_error}")
                    error_messages = {
                        "INVALID_PUBLIC_TOKEN": "Bank connection expired, please reconnect",
                        "INVALID_CREDENTIALS": "Bank credentials invalid",
                        "INSTITUTION_DOWN": "Bank service temporarily unavailable",
                    }
                    msg = error_messages.get(plaid_error, f"Bank connection failed: {plaid_error}")
                    return http_response(400, {"message": msg, "plaidError": plaid_error})
                else:
                    raise

        access_token = result["access_token"]
        secret_name = f"plaid/access-token/{user_id}"

        try:
            secrets.create_secret(
                Name=secret_name,
                SecretString=json.dumps({
                    "accessToken": access_token,
                    "env": creds["env"],
                    "connectedAt": datetime.now(timezone.utc).isoformat(),
                }),
            )
        except secrets.exceptions.ResourceExistsException:
            secrets.update_secret(
                SecretId=secret_name,
                SecretString=json.dumps({
                    "accessToken": access_token,
                    "env": creds["env"],
                    "connectedAt": datetime.now(timezone.utc).isoformat(),
                }),
            )

        return http_response(200, {
            "message": "Bank account connected successfully",
        })

    except Exception as e:
        print(f"Error: {str(e)}")
        return http_response(500, {"message": "Internal server error"})
