import time

from share_common import (
    build_display_name,
    get_claims,
    http_response,
    shares_table,
)


def _parse_body(event):
    raw_body = event.get("body")
    if not raw_body:
        return {}
    try:
        import json

        return json.loads(raw_body)
    except (ValueError, TypeError):
        return {}


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return http_response(200, {"ok": True})

    claims = get_claims(event)
    owner_id = claims.get("sub")
    if not owner_id:
        return http_response(401, {"message": "Unauthorized"})

    body = _parse_body(event)
    viewer_id = (body.get("viewerId") or "").strip()
    viewer_email = (body.get("viewerEmail") or "").strip()
    viewer_name = (body.get("viewerName") or "").strip()

    if not viewer_id:
        return http_response(400, {"message": "Missing required field: viewerId"})

    if viewer_id == owner_id:
        return http_response(400, {"message": "You cannot share receipts with yourself."})

    owner_email = claims.get("email", "")
    owner_name = build_display_name(
        claims.get("given_name"), claims.get("family_name"), owner_email
    )

    if not viewer_name:
        viewer_name = viewer_email or viewer_id

    item = {
        "ownerId": owner_id,
        "viewerId": viewer_id,
        "viewerEmail": viewer_email,
        "viewerName": viewer_name,
        "ownerEmail": owner_email,
        "ownerName": owner_name,
        "createdAt": int(time.time()),
    }

    try:
        shares_table.put_item(Item=item)
    except Exception as error:  # noqa: BLE001
        print(f"Error sharing receipts for owner {owner_id}: {str(error)}")
        return http_response(500, {"message": "Internal server error"})

    return http_response(201, {"message": "Share created", "share": item})
