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
        creds = get_plaid_creds()
        base_url = PLAID_URLS.get(creds["env"], PLAID_URLS["sandbox"])

        payload = json.dumps({
            "client_id": creds["clientId"],
            "secret": creds["secret"],
            "user": {"client_user_id": user_id},
            "client_name": "FinSight",
            "products": ["transactions"],
            "country_codes": ["US", "AT", "DE"],
            "language": "en",
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{base_url}/link/token/create",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())

        return http_response(200, {"linkToken": result["link_token"]})

    except Exception as e:
        print(f"Error: {str(e)}")
        return http_response(500, {"message": str(e)})