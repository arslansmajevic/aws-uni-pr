import os

import boto3
from botocore.config import Config

BUCKET_NAME = os.environ.get("BUCKET_NAME", "receipt-storage-bucket")

s3_client = boto3.client(
    "s3",
    region_name=os.environ.get("AWS_REGION", "eu-central-1"),
    config=Config(signature_version="s3v4"),
)


def generate_presigned_url(s3_key):
    try:
        return s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": s3_key},
            ExpiresIn=3600,
        )
    except Exception as error:  # noqa: BLE001
        print(f"Failed to generate presigned URL for {s3_key}: {str(error)}")
        return None


def primary_image_key(receipt):
    return (
        receipt.get("s3ObjectKey")
        or receipt.get("key")
        or receipt.get("objectKey")
    )


def collect_image_keys(receipt):
    """Return an ordered, de-duplicated list of S3 keys for a receipt."""
    image_keys = receipt.get("imageKeys")
    if not isinstance(image_keys, list):
        image_keys = []

    ordered = []
    for key in [primary_image_key(receipt), *image_keys]:
        if key and key not in ordered:
            ordered.append(key)

    return ordered


def normalize_receipt_items(receipt):
    items = receipt.get("receiptItems") or receipt.get("lineItems") or []

    if not isinstance(items, list):
        return []

    normalized_items = []
    for item in items:
        if not isinstance(item, dict):
            continue

        price = (
            item.get("lineTotal")
            or item.get("price")
            or receipt.get("totalAmount")
            or "0"
        )

        normalized_items.append(
            {
                "name": item.get("name") or item.get("description") or "Item",
                "quantity": item.get("quantity") or "1",
                "unitPrice": item.get("unitPrice"),
                "lineTotal": item.get("lineTotal"),
                "price": price,
                "discount": item.get("discount"),
                "productCode": item.get("productCode"),
            }
        )

    if not normalized_items and receipt.get("totalAmount"):
        normalized_items.append(
            {
                "name": receipt.get("merchantName") or "Receipt total",
                "quantity": "1",
                "price": receipt.get("totalAmount"),
                "lineTotal": receipt.get("totalAmount"),
            }
        )

    return normalized_items
