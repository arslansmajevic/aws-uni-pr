import os

import boto3
from boto3.dynamodb.conditions import Key

from share_common import get_user_id, http_response, is_shared
from receipt_helpers import generate_presigned_url, primary_image_key

dynamodb = boto3.resource("dynamodb")
receipts_table = dynamodb.Table(os.environ["RECEIPTS_TABLE_NAME"])


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return http_response(200, {"ok": True})

    viewer_id = get_user_id(event)
    if not viewer_id:
        return http_response(401, {"message": "Unauthorized"})

    owner_id = (event.get("pathParameters") or {}).get("ownerId")
    if not owner_id:
        return http_response(400, {"message": "Missing required path parameter: ownerId"})

    try:
        if not is_shared(owner_id, viewer_id):
            return http_response(403, {"message": "You do not have access to these receipts."})

        result = receipts_table.query(
            KeyConditionExpression=Key("userId").eq(owner_id)
        )
        receipts = result.get("Items", [])

        for receipt in receipts:
            s3_key = primary_image_key(receipt)
            receipt["imageUrl"] = generate_presigned_url(s3_key) if s3_key else None

        return http_response(200, {"receipts": receipts, "count": len(receipts)})
    except Exception as error:  # noqa: BLE001
        print(f"Error fetching shared receipts for owner {owner_id}: {str(error)}")
        return http_response(500, {"message": "Internal server error"})
