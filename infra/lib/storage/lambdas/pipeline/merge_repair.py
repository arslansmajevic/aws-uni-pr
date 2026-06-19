"""
Merge repair Lambda: apply validated Bedrock patches to the normalized receipt.

Loads the normalized data and the validated repair patch from S3.
Applies only approved patch fields to the existing indexed items.
Preserves the original Textract sourceConfidence on each field and
records repairConfidence per changed field.
Saves the updated normalized data back to S3.

After merging, the pipeline runs Validate again on the updated data.
"""

import json
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import boto3

s3_client = boto3.client("s3")

BUCKET_NAME = os.environ["BUCKET_NAME"]

PATCHABLE_FIELDS = {"name", "quantity", "unit", "unitPrice", "lineTotal", "discount", "productCode"}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def handler(event, context):
    """
    Reads normalizedDataKey and repairKey from event.
    Applies patches, saves updated normalized.json to S3.
    Injects repairAttempted=True so the next Validate run does not
    trigger another repair cycle.
    """
    user_id = event["userId"]
    receipt_id = event["receiptId"]
    normalized_key = event["normalizedDataKey"]
    repair_key = event["repairKey"]

    print(f"[MergeRepair] Merging repair for receipt {receipt_id}")

    # Load normalized data.
    norm_obj = s3_client.get_object(Bucket=BUCKET_NAME, Key=normalized_key)
    normalized = json.loads(norm_obj["Body"].read())

    # Load repair patches.
    repair_obj = s3_client.get_object(Bucket=BUCKET_NAME, Key=repair_key)
    repair_data = json.loads(repair_obj["Body"].read())
    patches = repair_data.get("patches", [])

    items = normalized.get("receiptItems", [])
    applied_count = 0
    audit_trail = []

    for patch in patches:
        idx = patch.get("itemIndex")
        field = patch.get("field")
        value = patch.get("value")
        confidence = patch.get("confidence")
        reason = patch.get("reason", "")

        # Validation (defensive — patches were already validated by repair Lambda).
        if not isinstance(idx, int) or idx < 0 or idx >= len(items):
            print(f"[MergeRepair] Skipping out-of-range index {idx}")
            continue
        if field not in PATCHABLE_FIELDS:
            print(f"[MergeRepair] Skipping unknown field {field!r}")
            continue
        if value is None:
            print(f"[MergeRepair] Skipping null patch for items[{idx}].{field}")
            continue

        item = items[idx]
        original_value = item.get(field)

        item[field] = value

        # Track per-field repair metadata.
        if "repairMeta" not in item:
            item["repairMeta"] = {}
        item["repairMeta"][field] = {
            "originalValue": original_value,
            "repairedValue": value,
            "repairConfidence": confidence,
            "reason": reason[:200],
        }

        if confidence is not None:
            item["repairConfidence"] = round(
                min(confidence, item.get("repairConfidence", 1.0)), 4
            )

        audit_trail.append({
            "itemIndex": idx,
            "field": field,
            "originalValue": original_value,
            "repairedValue": value,
            "confidence": confidence,
        })
        applied_count += 1

    print(f"[MergeRepair] Applied {applied_count}/{len(patches)} patches")

    normalized["receiptItems"] = items
    normalized["repairApplied"] = True
    normalized["repairPatchCount"] = applied_count
    normalized["mergedAt"] = now_iso()

    # Overwrite the normalized data key with the repaired version.
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=normalized_key,
        Body=json.dumps(normalized, default=str),
        ContentType="application/json",
    )

    # Save audit trail separately.
    audit_key = f"raw-extractions/{user_id}/{receipt_id}/repair_audit.json"
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=audit_key,
        Body=json.dumps(
            {"auditTrail": audit_trail, "mergedAt": now_iso()},
            default=str,
        ),
        ContentType="application/json",
    )

    return {
        **event,
        # Signal to the next Validate call that repair has been attempted.
        "repairAttempted": True,
        "mergedAt": now_iso(),
    }
