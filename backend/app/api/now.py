from datetime import datetime, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession
from app.config import settings
from app.models import Event, Schedule
from app.services.now import AirMedia, EventLike, ScheduleLike, resolve_now

router = APIRouter(tags=["now"])


async def compute_now(session: DbSession) -> dict[str, str]:
    tz = ZoneInfo(settings.tz)
    now = datetime.now(tz=tz)
    day_start = datetime.combine(now.date(), time.min, tzinfo=tz)
    day_end = datetime.combine(now.date(), time.max, tzinfo=tz)

    events_rows = (
        await session.execute(select(Event).options(selectinload(Event.media)))
    ).scalars().all()
    schedule_rows = (
        await session.execute(
            select(Schedule)
            .options(selectinload(Schedule.media))
            .where(Schedule.start_at >= day_start, Schedule.start_at <= day_end)
        )
    ).scalars().all()

    events = [
        EventLike(
            start_at=e.start_at,
            duration=e.duration,
            media=AirMedia(
                id=e.media.id,
                type=e.media.type,
                ready=e.media.status == "ready",
            ),
            until_midnight=bool(e.until_midnight),
        )
        for e in events_rows
        if e.media is not None
    ]
    schedule = [
        ScheduleLike(
            start_at=s.start_at,
            media=AirMedia(
                id=s.media.id,
                type=s.media.type,
                ready=s.media.status == "ready",
            ),
        )
        for s in schedule_rows
        if s.media is not None
    ]
    return resolve_now(now, events, schedule)


@router.get("/api/now")
async def api_now(session: DbSession) -> dict[str, str]:
    return await compute_now(session)
