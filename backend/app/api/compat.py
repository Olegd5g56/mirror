"""POST /api.php for the TV client. Only action=whatNow, no auth."""

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import DbSession
from app.api.now import compute_now

router = APIRouter(tags=["compat"])


@router.post("/api.php")
async def php_shim(request: Request, session: DbSession) -> dict:
    try:
        body = await request.json()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"status": "fail", "error": "Invalid JSON"},
        ) from e

    action = body.get("action") if isinstance(body, dict) else None
    if action != "whatNow":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"status": "fail", "error": f"action '{action}' unknown"},
        )
    return await compute_now(session)
