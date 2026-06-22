import json
import os

import boto3
from boto3.dynamodb.conditions import Key

SHARES_TABLE_NAME = os.environ.get("SHARES_TABLE_NAME", "receipt-shares")
VIEWER_INDEX_NAME = os.environ.get("VIEWER_INDEX_NAME", "ViewerIndex")

dynamodb = boto3.resource("dynamodb")
shares_table = dynamodb.Table(SHARES_TABLE_NAME)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
}


def http_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body, default=str),
    }


def get_claims(event):
    try:
        return event["requestContext"]["authorizer"]["claims"]
    except (KeyError, TypeError):
        return {}


def get_user_id(event):
    claims = get_claims(event)
    return claims.get("sub") or None


def build_display_name(given_name, family_name, email):
    """Return a human friendly name, falling back to the email address."""
    name = " ".join(part for part in [given_name, family_name] if part).strip()
    return name or email or ""


def is_shared(owner_id, viewer_id):
    """Return True when ``owner_id`` shares their receipts with ``viewer_id``."""
    if not owner_id or not viewer_id:
        return False

    result = shares_table.get_item(
        Key={"ownerId": owner_id, "viewerId": viewer_id}
    )
    return "Item" in result


def list_viewers(owner_id):
    """List the users an owner shares their receipts with."""
    result = shares_table.query(
        KeyConditionExpression=Key("ownerId").eq(owner_id)
    )
    return result.get("Items", [])


def list_owners(viewer_id):
    """List the owners that share their receipts with a viewer."""
    result = shares_table.query(
        IndexName=VIEWER_INDEX_NAME,
        KeyConditionExpression=Key("viewerId").eq(viewer_id),
    )
    return result.get("Items", [])
