from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, func, select

from app.api.deps import CurrentUser, DbSession
from app.config import settings
from app.models import Event, Media, Schedule
from app.schemas.media import MediaOut, media_to_out
from app.services.media_files import remove_artifacts

router = APIRouter(prefix="/api/media", tags=["media"])


async def _usage(session: DbSession, media_id: int) -> tuple[int, int]:
    ev = await session.scalar(
        select(func.count()).select_from(Event).where(Event.media_id == media_id)
    )
    sch = await session.scalar(
        select(func.count()).select_from(Schedule).where(Schedule.media_id == media_id)
    )
    return int(ev or 0), int(sch or 0)


@router.get("", response_model=list[MediaOut])
async def list_media(session: DbSession, user: CurrentUser) -> list[MediaOut]:
    rows = (
        await session.execute(select(Media).order_by(Media.created_at.desc()))
    ).scalars().all()
    out: list[MediaOut] = []
    for row in rows:
        ev, sch = await _usage(session, row.id)
        out.append(media_to_out(row, events_count=ev, schedule_count=sch))
    return out


@router.get("/{media_id}", response_model=MediaOut)
async def get_media(media_id: int, session: DbSession, user: CurrentUser) -> MediaOut:
    row = await session.get(Media, media_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Файл не знайдено")
    ev, sch = await _usage(session, row.id)
    return media_to_out(row, events_count=ev, schedule_count=sch)


@router.delete("/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(media_id: int, session: DbSession, user: CurrentUser) -> None:
    # Той самий FOR UPDATE, що й публікація у воркері: або рядок ще наш і ми
    # знімаємо його до перейменування в air/, або воркер уже встиг опублікувати
    # і ми стираємо вже цілий файл.
    row = await session.get(Media, media_id, with_for_update=True)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Файл не знайдено")
    extra = (row.thumb_path, row.poster_path)
    await session.execute(delete(Schedule).where(Schedule.media_id == media_id))
    await session.execute(delete(Event).where(Event.media_id == media_id))
    await session.delete(row)
    await session.commit()
    remove_artifacts(Path(settings.media_root), media_id, extra=extra)
