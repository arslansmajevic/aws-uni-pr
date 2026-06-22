from share_common import (
    get_user_id,
    http_response,
    list_owners,
)


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return http_response(200, {"ok": True})

    viewer_id = get_user_id(event)
    if not viewer_id:
        return http_response(401, {"message": "Unauthorized"})

    try:
        owners = list_owners(viewer_id)
    except Exception as error:  # noqa: BLE001
        print(f"Error listing owners for viewer {viewer_id}: {str(error)}")
        return http_response(500, {"message": "Internal server error"})

    return http_response(200, {"owners": owners, "count": len(owners)})
