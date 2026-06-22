from share_common import (
    get_user_id,
    http_response,
    shares_table,
)


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return http_response(200, {"ok": True})

    owner_id = get_user_id(event)
    if not owner_id:
        return http_response(401, {"message": "Unauthorized"})

    viewer_id = (event.get("pathParameters") or {}).get("viewerId")
    if not viewer_id:
        return http_response(400, {"message": "Missing required path parameter: viewerId"})

    try:
        shares_table.delete_item(
            Key={"ownerId": owner_id, "viewerId": viewer_id}
        )
    except Exception as error:  # noqa: BLE001
        print(f"Error removing share for owner {owner_id}: {str(error)}")
        return http_response(500, {"message": "Internal server error"})

    return http_response(200, {"message": "Share removed"})
