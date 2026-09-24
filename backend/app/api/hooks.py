"""Webhook endpoints для tusd: pre-create і pre-finish."""

from __future__ import annotations

import hmac
import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select

from app.api.deps import DbSession
from app.config import settings
from app.enums import MediaStatus, MediaType
from app.models import Media, User
from app.services.security import JWTDecodeError, decode_jwt
from app.services.uploads import safe_unlink

router = APIRouter(prefix="/api/hooks", tags=["hooks"])
log = logging.getLogger(__name__)

ALLOWED_MIME = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "video/mp4",
    "video/webm",
    "video/quicktime",
}
BLOCKED_EXT = {".svg", ".svgz", ".html", ".htm", ".xhtml", ".xml"}

_OK: dict[str, Any] = {"HTTPResponse": {"StatusCode": 200}}


def _reject(reason: str, code: int = 400) -> dict[str, Any]:
    return {
        "RejectUpload": True,
        "HTTPResponse": {
            "StatusCode": code,
            "Body": json.dumps({"error": reason}, ensure_ascii=False),
            "Header": {"Content-Type": "application/json"},
        },
    }


@router.post("/tusd")
async def tusd_hook(
    request: Request,
    session: DbSession,
    secret: str = Query(default=""),
) -> dict[str, Any]:
    if not hmac.compare_digest(secret, settings.tusd_hook_secret):
        log.warning("tusd webhook: bad secret")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad secret")

    payload = json.loads(await request.body())
    hook_type = payload.get("Type") or request.headers.get("hook-name", "")
    event = payload.get("Event") or {}
    upload = event.get("Upload") or {}
    metadata = upload.get("MetaData") or {}

    if hook_type == "pre-create":
        return await _on_pre_create(session, metadata)
    if hook_type == "pre-finish":
        return await _on_pre_finish(session, upload, metadata)
    return _OK


async def _on_pre_create(session, metadata: dict[str, str]) -> dict[str, Any]:
    token = metadata.get("auth_token")
    if not token:
        return _reject("Завантаження без токена авторизації", code=401)
    try:
        user_id = decode_jwt(token)
    except JWTDecodeError:
        return _reject("Недійсний або прострочений токен авторизації", code=401)
    if await session.get(User, user_id) is None:
        return _reject("Користувача не знайдено", code=401)

    mime = (metadata.get("filetype") or "").lower()
    if mime not in ALLOWED_MIME:
        shown = mime or "(порожньо)"
        return _reject(f"Тип файлу не дозволено: {shown}", code=415)

    filename = (metadata.get("filename") or "").lower()
    _, ext = os.path.splitext(filename)
    if ext in BLOCKED_EXT:
        return _reject(f"Розширення {ext} не дозволено", code=415)

    name = (metadata.get("name") or "").strip()
    if not name:
        name = os.path.splitext(metadata.get("filename") or "")[0].strip()
    if not name:
        return _reject("Потрібна назва файлу", code=400)

    existing = await session.scalar(select(Media.id).where(Media.name == name))
    if existing is not None:
        return _reject("Назва вже зайнята", code=409)

    return _OK


async def _on_pre_finish(
    session, upload: dict[str, Any], metadata: dict[str, str]
) -> dict[str, Any]:
    upload_id = upload.get("ID")
    if not upload_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "missing upload id")
    size = int(upload.get("Size") or 0)

    token = metadata.get("auth_token")
    try:
        user_id = decode_jwt(token or "", verify_exp=False)
    except JWTDecodeError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid auth_token: {e}") from e

    filename = metadata.get("filename") or upload_id
    mime = (metadata.get("filetype") or "application/octet-stream").lower()
    name = (metadata.get("name") or "").strip() or os.path.splitext(filename)[0].strip()

    media_root = Path(settings.media_root)
    temp_file = media_root / "temp" / upload_id
    info_file = media_root / "temp" / f"{upload_id}.info"
    if not temp_file.exists():
        log.warning("pre-finish replay (file already gone): %s", upload_id)
        return _OK

    kind = "video" if mime.startswith("video/") else "image"
    media = Media(
        name=name,
        type=kind if kind in (MediaType.image.value, MediaType.video.value) else MediaType.image.value,
        status=MediaStatus.pending.value,
        progress=0,
        mime_type=mime,
        size_bytes=size,
        uploaded_by=user_id,
    )
    session.add(media)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        await safe_unlink(temp_file)
        await safe_unlink(info_file)
        return _reject("Не вдалося зберегти файл (можливо, назва вже зайнята)", code=409)

    # Перейменовуємо temp → temp/{media_id}.incoming, щоб воркер знав id.
    incoming = media_root / "temp" / f"{media.id}.incoming"
    try:
        temp_file.replace(incoming)
    except OSError as e:
        log.error("failed to move tus temp: %s", e)
        media.status = MediaStatus.failed.value
        await session.commit()
        return _reject("Не вдалося зберегти файл на диск", code=500)
    await safe_unlink(info_file)

    from app.tasks.media_processing import process_media

    process_media.delay(media.id)
    log.info("media queued id=%s name=%s mime=%s", media.id, name, mime)
    return _OK
