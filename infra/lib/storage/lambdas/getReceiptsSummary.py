import os
import json
import boto3
from boto3.dynamodb.conditions import Key
from collections import defaultdict

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["RECEIPTS_TABLE_NAME"])

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
}

def http_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body, default=str),
    }

def get_user_id(event):
    try:
        return event["requestContext"]["authorizer"]["claims"]["sub"]
    except (KeyError, TypeError):
        return None

def parse_amount(value):
    if not value:
        return 0.0
    try:
        cleaned = str(value)\
            .replace(",", ".")\
            .replace("CHF", "")\
            .replace("$", "")\
            .replace("€", "")\
            .strip()
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0

def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return http_response(200, {"ok": True})

    user_id = get_user_id(event)
    if not user_id:
        return http_response(401, {"message": "Unauthorized"})

    try:
        result = table.query(
            KeyConditionExpression=Key("userId").eq(user_id)
        )
        receipts = result.get("Items", [])

        by_category = defaultdict(lambda: {"count": 0, "totalSpend": 0.0})
        total_spend = 0.0
        matched_count = 0
        unmatched_count = 0
        categorized_count = 0

        for receipt in receipts:
            status = receipt.get("processingStatus", "")

            if status == "FAILED":
                continue

            category = receipt.get("category", "Other")
            amount = parse_amount(receipt.get("totalAmount"))

            by_category[category]["count"] += 1
            by_category[category]["totalSpend"] = round(
                by_category[category]["totalSpend"] + amount, 2
            )
            total_spend += amount

            match_status = receipt.get("transactionMatchStatus", "PENDING")
            if match_status == "MATCHED":
                matched_count += 1
            elif match_status == "UNMATCHED":
                unmatched_count += 1

            if status == "CATEGORIZED" or match_status in ("MATCHED", "UNMATCHED", "POSSIBLE_MATCH"):
                categorized_count += 1

        return http_response(200, {
            "summary": {
                "totalReceipts": len(receipts),
                "categorizedReceipts": categorized_count,
                "totalSpend": round(total_spend, 2),
                "matchedCount": matched_count,
                "unmatchedCount": unmatched_count,
                "byCategory": dict(by_category),
            }
        })

    except Exception as e:
        print(f"Error generating summary for user {user_id}: {str(e)}")
        return http_response(500, {"message": "Internal server error"})