"""Логіка ефіру: що зараз має крутитись на екрані.

Чисті функції без БД — їх покривають unit-тести. SQL-шар у api/compat.py
і api/now.py лише дістає рядки і віддає сюди.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

KYIV = ZoneInfo("Europe/Kyiv")
DEFAULT_PATH = "media/default.jpg"
SECONDS_IN_DAY = 24 * 60 * 60


class DurationError(ValueError):
    pass


def parse_mmss(value: str) -> timedelta:
    """'MM:SS' або 'HH:MM:SS' → timedelta. 0 і ≥ 24 год — помилка."""
    if not isinstance(value, str):
        raise DurationError("Тривалість: ГГ:ХХ:СС або ХХ:СС")
    parts = value.split(":")
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        raise DurationError("Тривалість: ГГ:ХХ:СС або ХХ:СС")
    if len(parts) == 2:
        hours = 0
        minutes, seconds = int(parts[0]), int(parts[1])
    else:
        hours, minutes, seconds = (int(p) for p in parts)
    if hours > 23 or minutes > 59 or seconds > 59:
        raise DurationError("Години 0–23, хвилини і секунди 0–59")
    total = hours * 3600 + minutes * 60 + seconds
    if total == 0:
        raise DurationError("Тривалість має бути більшою за нуль")
    if total >= SECONDS_IN_DAY:
        raise DurationError("Подія не може тривати добу або довше")
    return timedelta(seconds=total)


def format_mmss(td: timedelta) -> str:
    total = int(td.total_seconds())
    if total < 0:
        total = 0
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def time_to_sec(t: time) -> int:
    return t.hour * 3600 + t.minute * 60 + t.second


def event_windows(start: time, duration: timedelta) -> list[tuple[int, int]]:
    """Напіввідкриті [start, end) у секундах від півночі. Wrap → два інтервали."""
    start_s = time_to_sec(start)
    dur_s = int(duration.total_seconds())
    end_s = start_s + dur_s
    if end_s <= SECONDS_IN_DAY:
        return [(start_s, end_s)]
    return [(start_s, SECONDS_IN_DAY), (0, end_s - SECONDS_IN_DAY)]


def end_clock(start: time, duration: timedelta, until_midnight: bool = False) -> time:
    """Час закінчення для відображення «від–до»."""
    if until_midnight:
        return time(23, 59)
    total = (time_to_sec(start) + int(duration.total_seconds())) % SECONDS_IN_DAY
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    return time(hours, minutes, seconds)


def window_from_range(start: time, end: time) -> tuple[timedelta, bool]:
    """(duration, until_midnight). Кінець 23:59 = до кінця доби."""
    if start == end:
        raise DurationError("Початок і кінець не можуть збігатися")
    if end.hour == 23 and end.minute == 59:
        return duration_until_midnight(start), True
    start_s = time_to_sec(start)
    end_s = time_to_sec(end)
    if end_s > start_s:
        dur_s = end_s - start_s
    else:
        dur_s = SECONDS_IN_DAY - start_s + end_s
    if dur_s <= 0 or dur_s >= SECONDS_IN_DAY:
        raise DurationError("Некоректне вікно")
    return timedelta(seconds=dur_s), False


def duration_until_midnight(start: time) -> timedelta:
    """Від start до 24:00. Менше 24 год, щоб пройти CHECK на duration."""
    left = SECONDS_IN_DAY - time_to_sec(start)
    if left >= SECONDS_IN_DAY:
        left = SECONDS_IN_DAY - 1
    if left <= 0:
        left = 1
    return timedelta(seconds=left)


def effective_duration(
    start: time, duration: timedelta, until_midnight: bool = False
) -> timedelta:
    if until_midnight:
        return duration_until_midnight(start)
    return duration


def event_is_active(
    now: time,
    start: time,
    duration: timedelta,
    until_midnight: bool = False,
) -> bool:
    now_s = time_to_sec(now)
    if until_midnight:
        return now_s >= time_to_sec(start)
    return any(a <= now_s < b for a, b in event_windows(start, duration))


def windows_overlap(
    a_start: time, a_dur: timedelta, b_start: time, b_dur: timedelta
) -> bool:
    for s1, e1 in event_windows(a_start, a_dur):
        for s2, e2 in event_windows(b_start, b_dur):
            if s1 < e2 and s2 < e1:
                return True
    return False


@dataclass(frozen=True)
class AirMedia:
    id: int
    type: str  # image | video
    ready: bool = True


@dataclass(frozen=True)
class EventLike:
    start_at: time
    duration: timedelta
    media: AirMedia
    until_midnight: bool = False


@dataclass(frozen=True)
class ScheduleLike:
    start_at: datetime
    media: AirMedia


def air_payload(media: AirMedia) -> dict[str, str]:
    ext = "mp4" if media.type == "video" else "jpg"
    return {"type": media.type, "path": f"media/{media.id}.{ext}"}


def resolve_now(
    now: datetime,
    events: list[EventLike],
    schedule: list[ScheduleLike],
    default_path: str = DEFAULT_PATH,
) -> dict[str, str]:
    """Пріоритет: активна подія → останній слот сьогодні → default.

    `now` може бути naive (вважаємо Київ) або aware.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=KYIV)
    else:
        now = now.astimezone(KYIV)

    now_t = now.time().replace(tzinfo=None)

    active = [
        e
        for e in events
        if e.media.ready
        and event_is_active(now_t, e.start_at, e.duration, e.until_midnight)
    ]
    if active:
        chosen = max(active, key=lambda e: time_to_sec(e.start_at))
        return air_payload(chosen.media)

    today = now.date()
    candidates = []
    for item in schedule:
        if not item.media.ready:
            continue
        start = item.start_at
        if start.tzinfo is None:
            start = start.replace(tzinfo=KYIV)
        else:
            start = start.astimezone(KYIV)
        if start.date() == today and start <= now:
            candidates.append((start, item))
    if candidates:
        _, item = max(candidates, key=lambda pair: pair[0])
        return air_payload(item.media)

    return {"type": "image", "path": default_path}
