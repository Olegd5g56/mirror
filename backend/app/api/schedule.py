from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.config import settings
from app.enums import MediaStatus
from app.models import Media, Schedule
from app.schemas.schedule import ScheduleCreate, ScheduleOut

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.tz)


def _as_kyiv(dt: datetime) -> datetime:
    tz = _tz()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def _day_range(day: date) -> tuple[datetime, datetime]:
    tz = _tz()
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = datetime.combine(day, time.max, tzinfo=tz)
    return start, end


@router.get("", response_model=list[ScheduleOut])
async def list_schedule(
    session: DbSession,
    user: CurrentUser,
    date: date | None = Query(default=None),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
) -> list[ScheduleOut]:
    stmt = select(Schedule).options(selectinload(Schedule.media)).order_by(Schedule.start_at)
    if date is not None:
        start, end = _day_range(date)
        stmt = stmt.where(Schedule.start_at >= start, Schedule.start_at <= end)
    elif date_from is not None and date_to is not None:
        start, _ = _day_range(date_from)
        _, end = _day_range(date_to)
        stmt = stmt.where(Schedule.start_at >= start, Schedule.start_at <= end)
    rows = (await session.execute(stmt)).scalars().all()
    return [ScheduleOut.from_row(r) for r in rows]


@router.post("", response_model=ScheduleOut, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    body: ScheduleCreate, session: DbSession, user: CurrentUser
) -> ScheduleOut:
    media = await session.get(Media, body.media_id)
    if media is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Файл не знайдено")
    if media.status != MediaStatus.ready.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Файл ще обробляється і не готовий до ефіру",
        )

    start_at = _as_kyiv(body.start_at)
    row = Schedule(media_id=body.media_id, start_at=start_at)
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Цей час уже зайнятий") from e

    row = (
        await session.execute(
            select(Schedule)
            .options(selectinload(Schedule.media))
            .where(Schedule.id == row.id)
        )
    ).scalar_one()
    return ScheduleOut.from_row(row)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: int, session: DbSession, user: CurrentUser
) -> None:
    row = await session.get(Schedule, schedule_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Слот не знайдено")
    await session.delete(row)
    await session.commit()
    return None
