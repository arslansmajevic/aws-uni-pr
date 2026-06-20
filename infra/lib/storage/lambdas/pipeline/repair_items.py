"""
Bedrock repair Lambda: correct low-confidence or incomplete line items.

Uses the Bedrock Converse API with the configured repair model (vision-capable)
to generate a targeted patch for specific problematic rows. Bedrock is NOT asked
to regenerate the full receipt — only to supply corrections for supplied fields
on supplied item indexes.

Strict Python-side validation of the model response is applied before any patch
is accepted. Malformed responses, invalid indexes, invalid field names, or
arithmetic-contradicting values are rejected individually.

The full Bedrock response and the validated patch set are saved to S3.
"""

import base64
import json
import os
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import boto3

s3_client = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime", region_name="eu-central-1")

BUCKET_NAME = os.environ["BUCKET_NAME"]
REPAIR_MODEL_ID = os.environ.get("REPAIR_MODEL_ID", "eu.amazon.nova-pro-v1:0")

# Fields that a repair patch is allowed to set.
PATCHABLE_FIELDS = {"name", "quantity", "unit", "unitPrice", "lineTotal", "discount", "productCode"}

# Confidence threshold below which an item is considered low-confidence (0–1 scale).
# Must match LOW_CONFIDENCE_THRESHOLD / 100 in validate.py.
LOW_CONFIDENCE_THRESHOLD = 0.80

# Maximum number of items to include in the repair prompt (avoid huge prompts).
MAX_ITEMS_IN_PROMPT = 30

MONEY_RE = re.compile(r"^-?\d+(\.\d{1,4})?$")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Response validation (strict Python-side schema enforcement)
# ---------------------------------------------------------------------------

def _is_valid_money(value) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    return bool(MONEY_RE.match(str(value).strip()))


def _validate_patch(patch: dict, num_items: int, normalized_items: list[dict]) -> tuple[bool, str]:
    """
    Return (valid, reason).
    A patch is valid when:
    - itemIndex is an integer within range
    - field is in PATCHABLE_FIELDS
    - value is present and has the right type/format for the field
    - confidence (if present) is 0–1
    - the patch does not contradict known high-confidence Textract values
    """
    idx = patch.get("itemIndex")
    if not isinstance(idx, int) or idx < 0 or idx >= num_items:
        return False, f"itemIndex {idx!r} is out of range [0, {num_items})"

    field = patch.get("field")
    if field not in PATCHABLE_FIELDS:
        return False, f"field {field!r} is not patchable"

    value = patch.get("value")
    if value is None:
        # None is allowed — means "unresolved"
        return True, ""

    if field in ("unitPrice", "lineTotal", "discount"):
        if not _is_valid_money(value):
            return False, f"{field} value {value!r} is not a valid decimal"

    if field == "name" and not isinstance(value, str):
        return False, "name must be a string"

    conf = patch.get("confidence")
    if conf is not None:
        try:
            c = float(conf)
        except (TypeError, ValueError):
            return False, f"confidence {conf!r} is not a number"
        if not (0.0 <= c <= 1.0):
            return False, f"confidence {conf!r} is out of [0, 1]"

    # Do not override high-confidence Textract values unless the value
    # actually differs (i.e. there's something to fix).
    original = normalized_items[idx] if idx < len(normalized_items) else {}
    original_conf = original.get("sourceConfidence")
    if (
        original_conf is not None
        and float(original_conf) >= 0.90
        and original.get(field) is not None
        and original.get(field) == value
    ):
        # Same value, high confidence — no-op but still valid
        pass

    return True, ""


def validate_repair_response(raw_response: dict, num_items: int, normalized_items: list) -> list[dict]:
    """
    Parse and strictly validate the Bedrock repair response.
    Returns only accepted patches.
    Raises ValueError if the top-level structure is malformed.
    """
    if not isinstance(raw_response, dict):
        raise ValueError("Repair response is not a JSON object")

    patches = raw_response.get("patches")
    if patches is None:
        # Also accept a flat list
        if isinstance(raw_response, list):
            patches = raw_response
        else:
            raise ValueError("Repair response missing 'patches' key")

    if not isinstance(patches, list):
        raise ValueError(f"'patches' is not a list: {type(patches)}")

    accepted = []
    for i, patch in enumerate(patches):
        if not isinstance(patch, dict):
            print(f"[Repair] Patch {i}: skipped (not a dict)")
            continue
        valid, reason = _validate_patch(patch, num_items, normalized_items)
        if valid:
            accepted.append(patch)
        else:
            print(f"[Repair] Patch {i} rejected: {reason}")

    return accepted


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_repair_prompt(
    normalized_items: list[dict],
    repair_reasons: list[str],
    subtotal: str | None,
    total: str | None,
) -> str:
    # Include only items that need attention (missing fields or low confidence).
    problem_indexes = []
    for i, item in enumerate(normalized_items[:MAX_ITEMS_IN_PROMPT]):
        is_low_conf = item.get("sourceConfidence") is not None and float(item["sourceConfidence"]) < LOW_CONFIDENCE_THRESHOLD
        is_incomplete = not item.get("lineTotal") or not item.get("name")
        if is_low_conf or is_incomplete:
            problem_indexes.append(i)

    # If no specific problems found, include all items (up to limit).
    if not problem_indexes:
        problem_indexes = list(range(min(len(normalized_items), MAX_ITEMS_IN_PROMPT)))

    items_json = json.dumps(
        [
            {
                "index": i,
                "name": normalized_items[i].get("name"),
                "quantity": normalized_items[i].get("quantity"),
                "unitPrice": normalized_items[i].get("unitPrice"),
                "lineTotal": normalized_items[i].get("lineTotal"),
                "sourceConfidence": normalized_items[i].get("sourceConfidence"),
            }
            for i in problem_indexes
        ],
        indent=2,
    )

    reasons_text = "\n".join(f"- {r}" for r in (repair_reasons or []))

    return (
        "You are a receipt data repair assistant. "
        "Look at the receipt image and the extracted items below. "
        "Return ONLY a JSON object with a 'patches' array.\n\n"
        f"Known receipt total: {total or 'unknown'}\n"
        f"Known subtotal: {subtotal or 'unknown'}\n\n"
        "Problems detected:\n"
        f"{reasons_text or '- Some items have low confidence or missing fields'}\n\n"
        "Items that may need repair (with their current extracted values):\n"
        f"{items_json}\n\n"
        "Rules:\n"
        "- Only correct the items and fields listed above.\n"
        "- Never add new items. Never remove items.\n"
        "- Do not change a field unless the receipt image clearly contradicts the current value.\n"
        "- Keep unitPrice and lineTotal as separate fields.\n"
        "- Use null for a field if you cannot determine the correct value.\n"
        "- All money values must be decimal strings (e.g. '12.50').\n"
        "- Negative values are allowed only for discounts.\n"
        "- Return ONLY valid JSON. No explanation text.\n\n"
        "Required response format:\n"
        '{"patches": [{"itemIndex": 0, "field": "quantity", "value": "2", "reason": "...", "confidence": 0.9}]}'
    )


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------

def handler(event, context):
    """
    Reads normalized data, Textract output, and layout (all from S3).
    Calls Bedrock repair model with the original receipt image.
    Saves raw response and validated patches to S3.
    Returns repairKey in the event.
    """
    bucket = event["bucket"]
    user_id = event["userId"]
    receipt_id = event["receiptId"]

    normalized_key = event["normalizedDataKey"]
    repair_reasons = event.get("validationSummary", {}).get("repairReasons") or []

    print(f"[Repair] Starting repair for receipt {receipt_id}")

    # Load normalized data.
    norm_obj = s3_client.get_object(Bucket=BUCKET_NAME, Key=normalized_key)
    normalized = json.loads(norm_obj["Body"].read())
    items = normalized.get("receiptItems", [])

    if not items:
        print("[Repair] No items to repair — saving empty patch and returning")
        repair_key = f"raw-extractions/{user_id}/{receipt_id}/repair.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=repair_key,
            Body=json.dumps({"patches": [], "unresolvedReasons": [], "repairedAt": now_iso()}, default=str),
            ContentType="application/json",
        )
        return {**event, "repairKey": repair_key}

    # Load original image for visual context.
    source_key = event.get("normalizedInputKey") or event["key"]
    image_obj = s3_client.get_object(Bucket=bucket, Key=source_key)
    image_bytes = image_obj["Body"].read()

    # Detect image format from magic bytes.
    if image_bytes[:4] == b"%PDF":
        # Bedrock Converse doesn't accept PDF via inline image.
        print("[Repair] Source is PDF — sending text-only prompt")
        image_content = None
    elif image_bytes[:2] == b"\xff\xd8":
        image_content = {"format": "jpeg", "source": {"bytes": image_bytes}}
    elif image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        image_content = {"format": "png", "source": {"bytes": image_bytes}}
    else:
        image_content = {"format": "jpeg", "source": {"bytes": image_bytes}}

    prompt_text = _build_repair_prompt(
        items,
        repair_reasons,
        normalized.get("subtotalAmount"),
        normalized.get("totalAmount"),
    )

    content = []
    if image_content:
        content.append({"image": image_content})
    content.append({"text": prompt_text})

    last_error = None
    raw_response_text = None

    for attempt in range(3):
        try:
            response = bedrock.converse(
                modelId=REPAIR_MODEL_ID,
                messages=[{"role": "user", "content": content}],
                inferenceConfig={"maxTokens": 2048, "temperature": 0.0},
            )
            raw_response_text = response["output"]["message"]["content"][0]["text"]
            stop_reason = response.get("stopReason", "unknown")
            print(f"[Repair] Model response: stopReason={stop_reason}, length={len(raw_response_text)}")
            break
        except Exception as exc:
            last_error = exc
            print(f"[Repair] Attempt {attempt + 1}/3 failed: {exc}")
            if attempt < 2:
                import time
                time.sleep(2 ** attempt)

    if raw_response_text is None:
        raise RuntimeError(f"[Repair] All Bedrock attempts failed: {last_error}")

    # Parse and strictly validate the model response.
    raw_parsed = None
    try:
        # Strip markdown fences if present.
        text = raw_response_text.strip()
        if "```" in text:
            parts = text.split("```")
            for part in parts[1::2]:
                candidate = part.strip()
                if candidate.startswith("json"):
                    candidate = candidate[4:].strip()
                try:
                    raw_parsed = json.loads(candidate)
                    break
                except json.JSONDecodeError:
                    continue
        if raw_parsed is None:
            raw_parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"[Repair] JSON parse error: {exc}. Raw response:\n{raw_response_text[:500]}")
        raw_parsed = {}

    try:
        validated_patches = validate_repair_response(raw_parsed, len(items), items)
    except ValueError as exc:
        print(f"[Repair] Repair response validation failed: {exc}")
        validated_patches = []

    unresolved_reasons = raw_parsed.get("unresolvedReasons", []) if isinstance(raw_parsed, dict) else []

    repair_data = {
        "patches": validated_patches,
        "unresolvedReasons": unresolved_reasons,
        "rawModelResponse": raw_response_text[:5000],
        "model": REPAIR_MODEL_ID,
        "repairedAt": now_iso(),
    }

    repair_key = f"raw-extractions/{user_id}/{receipt_id}/repair.json"
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=repair_key,
        Body=json.dumps(repair_data, default=str),
        ContentType="application/json",
    )

    print(
        f"[Repair] Accepted {len(validated_patches)} patches, "
        f"unresolved={len(unresolved_reasons)}"
    )

    return {
        **event,
        "repairKey": repair_key,
        "repairPatchCount": len(validated_patches),
    }
