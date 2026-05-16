import json
import boto3
import urllib.request

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

        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())

        access_token = result["access_token"]

        secret_name = f"plaid/access-token/{user_id}"
        try:
            secrets.create_secret(
                Name=secret_name,
                SecretString=json.dumps({
                    "accessToken": access_token,
                    "env": creds["env"],
                }),
            )
        except secrets.exceptions.ResourceExistsException:
            secrets.update_secret(
                SecretId=secret_name,
                SecretString=json.dumps({
                    "accessToken": access_token,
                    "env": creds["env"],
                }),
            )

        print(f"Bank connected for user: {user_id}")
        return http_response(200, {"message": "Bank account connected successfully"})

    except Exception as e:
        print(f"Error: {str(e)}")
        return http_response(500, {"message": str(e)})