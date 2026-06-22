from share_common import (
    get_user_id,
    http_response,
    list_viewers,
)


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return http_response(200, {"ok": True})

    owner_id = get_user_id(event)
    if not owner_id:
        return http_response(401, {"message": "Unauthorized"})

    try:
        viewers = list_viewers(owner_id)
    except Exception as error:  # noqa: BLE001
        print(f"Error listing viewers for owner {owner_id}: {str(error)}")
        return http_response(500, {"message": "Internal server error"})

    return http_response(200, {"viewers": viewers, "count": len(viewers)})
