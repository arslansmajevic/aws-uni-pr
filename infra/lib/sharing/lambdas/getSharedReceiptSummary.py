import os

import boto3

from share_common import get_user_id, http_response, is_shared
from receipt_helpers import (
    collect_image_keys,
    generate_presigned_url,
    normalize_receipt_items,
    primary_image_key,
)

dynamodb = boto3.resource("dynamodb")
receipts_table = dynamodb.Table(os.environ["RECEIPTS_TABLE_NAME"])


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return http_response(200, {"ok": True})

    viewer_id = get_user_id(event)
    if not viewer_id:
        return http_response(401, {"message": "Unauthorized"})

    path_params = event.get("pathParameters") or {}
    owner_id = path_params.get("ownerId")
    receipt_id = path_params.get("receiptId")
    if not owner_id or not receipt_id:
        return http_response(400, {"message": "Missing required path parameters"})

    try:
        if not is_shared(owner_id, viewer_id):
            return http_response(403, {"message": "You do not have access to this receipt."})

        result = receipts_table.get_item(
            Key={"userId": owner_id, "receiptId": receipt_id}
        )
        receipt = result.get("Item")
        if not receipt:
            return http_response(404, {"message": "Receipt not found"})

        image_keys = collect_image_keys(receipt)
        image_urls = [
            url
            for url in (generate_presigned_url(key) for key in image_keys)
            if url
        ]
        s3_key = primary_image_key(receipt)
        primary_url = image_urls[0] if image_urls else (
            generate_presigned_url(s3_key) if s3_key else None
        )

        response_body = {
            "receiptId": receipt.get("receiptId", receipt_id),
            "merchantName": receipt.get("merchantName"),
            "receiptDate": receipt.get("receiptDate"),
            "receiptTime": receipt.get("receiptTime"),
            "category": receipt.get("category"),
            "totalAmount": receipt.get("totalAmount"),
            "currency": receipt.get("currency") or "USD",
            "processingStatus": receipt.get("processingStatus"),
            "transactionMatchStatus": receipt.get("transactionMatchStatus"),
            "matchedTransactionName": receipt.get("matchedTransactionName"),
            "receiptItems": normalize_receipt_items(receipt),
            "imageUrl": primary_url,
            "imageUrls": image_urls,
        }

        return http_response(200, response_body)
    except Exception as error:  # noqa: BLE001
        print(f"Error loading shared receipt {receipt_id} for owner {owner_id}: {str(error)}")
        return http_response(500, {"message": "Internal server error"})
