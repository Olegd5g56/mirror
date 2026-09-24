from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.enums import MediaStatus
from app.models import Event, Media
from app.schemas.event import EventCreate, EventOut
from app.services.now import (
    DurationError,
    effective_duration,
    window_from_range,
    windows_overlap,
)

router = APIRouter(prefix="/api/events", tags=["events"])


async def _all_events(session: DbSession) -> list[Event]:
    stmt = select(Event).options(selectinload(Event.media)).order_by(Event.start_at)
    return list((await session.execute(stmt)).scalars().all())


@router.get("", response_model=list[EventOut])
async def list_events(session: DbSession, user: CurrentUser) -> list[EventOut]:
    return [EventOut.from_row(e) for e in await _all_events(session)]


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_event(
    body: EventCreate, session: DbSession, user: CurrentUser
) -> EventOut:
    media = await session.get(Media, body.media_id)
    if media is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Файл не знайдено")
    if media.status != MediaStatus.ready.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Файл ще обробляється і не готовий до ефіру",
        )

    try:
        duration, until_midnight = window_from_range(body.start_at, body.end_at)
    except DurationError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from e

    existing = await _all_events(session)
    for e in existing:
        if windows_overlap(
            body.start_at,
            effective_duration(body.start_at, duration, until_midnight),
            e.start_at,
            effective_duration(e.start_at, e.duration, e.until_midnight),
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Перетинається з подією «{e.name}»",
            )

    row = Event(
        name=body.name.strip(),
        start_at=body.start_at,
        duration=duration,
        until_midnight=until_midnight,
        media_id=body.media_id,
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        msg = str(e.orig) if e.orig is not None else str(e)
        if "events_name" in msg or "name" in msg:
            raise HTTPException(status.HTTP_409_CONFLICT, "Назва вже зайнята") from e
        if "start_at" in msg:
            raise HTTPException(status.HTTP_409_CONFLICT, "Цей час уже зайнятий") from e
        raise HTTPException(status.HTTP_409_CONFLICT, "Не вдалося зберегти подію") from e

    row = (
        await session.execute(
            select(Event).options(selectinload(Event.media)).where(Event.id == row.id)
        )
    ).scalar_one()
    return EventOut.from_row(row)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(event_id: int, session: DbSession, user: CurrentUser) -> None:
    row = await session.get(Event, event_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Подію не знайдено")
    await session.delete(row)
    await session.commit()
    return None
