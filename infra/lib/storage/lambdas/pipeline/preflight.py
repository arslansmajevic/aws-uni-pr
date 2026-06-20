"""
Preflight Lambda: validate and normalize the uploaded receipt file.

Checks:
- File is not empty and does not exceed the Textract size limit.
- File format is one Textract can process (JPEG, PNG, TIFF, PDF).
- Detects common unsupported mobile formats (WebP, HEIC/HEIF) and rejects
  them with a clear error message.

Saves a validated copy to normalized-inputs/ and returns the new key so
downstream stages always use a clean, verified source object.
"""

import os
from datetime import datetime, timezone

import boto3

s3_client = boto3.client("s3")

BUCKET_NAME = os.environ["BUCKET_NAME"]

# Textract supports images up to 10 MB and PDFs up to 500 pages / 500 MB.
# For safety we cap at 20 MB for all formats.
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB

# Magic-byte signatures used for format detection.
_SIGNATURES = {
    "jpeg": [(0, b"\xff\xd8\xff")],
    "png": [(0, b"\x89PNG\r\n\x1a\n")],
    "tiff_le": [(0, b"II\x2a\x00")],
    "tiff_be": [(0, b"MM\x00\x2a")],
    "pdf": [(0, b"%PDF")],
    "webp": [(0, b"RIFF"), (8, b"WEBP")],
    "heic": [(4, b"ftyp")],  # HEIC / HEIF / AVIF all use ftyp box
}

TEXTRACT_SUPPORTED = {"jpeg", "png", "tiff_le", "tiff_be", "pdf"}
UNSUPPORTED_MOBILE = {"webp", "heic"}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _detect_format(header: bytes) -> str:
    """
    Identify the file format from the first 16 bytes.
    Returns a format string or 'unknown'.
    """
    # WebP check requires two non-contiguous offsets.
    if len(header) >= 12 and header[0:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    for fmt, sigs in _SIGNATURES.items():
        if fmt == "webp":
            continue  # already handled above
        match = all(
            len(header) >= offset + len(sig) and header[offset:offset + len(sig)] == sig
            for offset, sig in sigs
        )
        if match:
            return fmt
    return "unknown"


def _validate_and_copy(bucket: str, key: str, normalized_key: str) -> tuple[str, str, int]:
    """
    Validate a single image key and copy it to normalized-inputs/.

    Returns (normalized_key, detected_format, file_size_bytes).
    Raises ValueError for empty / oversized / unsupported files.
    """
    head = s3_client.head_object(Bucket=bucket, Key=key)
    file_size = head.get("ContentLength", 0)

    if file_size == 0:
        raise ValueError(f"[Preflight] File is empty: {key}")

    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"[Preflight] File size {file_size} bytes exceeds the "
            f"{MAX_FILE_SIZE_BYTES // (1024*1024)} MB limit: {key}"
        )

    header_resp = s3_client.get_object(Bucket=bucket, Key=key, Range="bytes=0-15")
    header_bytes = header_resp["Body"].read()

    fmt = _detect_format(header_bytes)
    print(f"[Preflight] Detected format: {fmt} for {key}")

    if fmt in UNSUPPORTED_MOBILE:
        raise ValueError(
            f"[Preflight] Unsupported file format '{fmt}' for key {key}. "
            f"Please convert to JPEG, PNG, TIFF, or PDF before uploading."
        )

    if fmt not in TEXTRACT_SUPPORTED:
        raise ValueError(
            f"[Preflight] Unknown or unsupported file format for key {key}. "
            f"Supported formats: JPEG, PNG, TIFF, PDF."
        )

    ext_map = {"jpeg": "jpg", "png": "png", "tiff_le": "tiff", "tiff_be": "tiff", "pdf": "pdf"}
    ext = ext_map[fmt]

    # Derive the destination key: replace the suffix with the canonical extension.
    dest_key = f"{normalized_key}.{ext}"

    s3_client.copy_object(
        Bucket=bucket,
        CopySource={"Bucket": bucket, "Key": key},
        Key=dest_key,
        MetadataDirective="COPY",
    )

    print(f"[Preflight] Validated and copied {key} → {dest_key} (format={fmt}, size={file_size})")
    return dest_key, fmt, file_size


def handler(event, context):
    """
    Input event (single image):
    {
      "bucket": "...",
      "key":    "uploads/<userId>/<receiptId>/<filename>",
      "userId": "...",
      "receiptId": "..."
    }

    Input event (multi-image — keys array):
    {
      "bucket": "...",
      "key":    "uploads/<userId>/<receiptId>/image-0.jpg",   // primary
      "keys":   ["uploads/.../image-0.jpg", "uploads/.../image-1.jpg"],
      "userId": "...",
      "receiptId": "..."
    }

    Output event adds:
      "normalizedInputKey":  <first normalized key>    (backward compat)
      "normalizedInputKeys": [<key1>, <key2>, ...]     (all normalized keys)
    """
    bucket = event["bucket"]
    user_id = event["userId"]
    receipt_id = event["receiptId"]

    # Support both single-image (key) and multi-image (keys) paths.
    source_keys = event.get("keys") or [event["key"]]

    print(f"[Preflight] Validating {len(source_keys)} image(s) for receipt {receipt_id}")

    normalized_keys = []
    for i, key in enumerate(source_keys):
        # Build destination path with index suffix so names don't collide.
        dest_prefix = f"normalized-inputs/{user_id}/{receipt_id}/receipt-{i}"
        dest_key, fmt, file_size = _validate_and_copy(bucket, key, dest_prefix)
        normalized_keys.append(dest_key)

    return {
        **event,
        # Keep scalar for backward compat with single-image downstream stages.
        "normalizedInputKey": normalized_keys[0],
        # Full list consumed by multi-image-aware stages.
        "normalizedInputKeys": normalized_keys,
        "detectedFormat": fmt,
        "fileSizeBytes": file_size,
        "preflightAt": now_iso(),
    }
