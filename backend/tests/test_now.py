from datetime import datetime, time, timedelta

from app.services.now import (
    AirMedia,
    DurationError,
    EventLike,
    ScheduleLike,
    end_clock,
    event_is_active,
    format_mmss,
    parse_mmss,
    resolve_now,
    window_from_range,
    windows_overlap,
)

IMG = AirMedia(id=1, type="image", ready=True)
VID = AirMedia(id=8, type="video", ready=True)
NOT_READY = AirMedia(id=9, type="image", ready=False)


def test_parse_mmss_one_minute():
    assert parse_mmss("01:00") == timedelta(minutes=1)
    assert format_mmss(timedelta(minutes=1)) == "01:00"


def test_parse_mmss_five_seconds():
    assert parse_mmss("00:05") == timedelta(seconds=5)
    assert format_mmss(timedelta(seconds=5)) == "00:05"


def test_parse_hours():
    assert parse_mmss("04:00:00") == timedelta(hours=4)
    assert parse_mmss("1:00:00") == timedelta(hours=1)
    assert format_mmss(timedelta(hours=4)) == "04:00:00"


def test_parse_mmss_rejects_zero_and_day():
    for bad in ("00:00", "00:00:00", "60:00", "99:00", "24:00:00", "", "aa:bb", "01"):
        try:
            parse_mmss(bad)
        except DurationError:
            continue
        raise AssertionError(f"should reject {bad!r}")


def test_event_active_plain_window():
    start = time(8, 0, 0)
    dur = timedelta(minutes=5)
    assert event_is_active(time(8, 0, 0), start, dur)
    assert event_is_active(time(8, 3, 0), start, dur)
    assert not event_is_active(time(8, 5, 0), start, dur)
    assert not event_is_active(time(7, 59, 59), start, dur)


def test_event_active_midnight_wrap():
    start = time(23, 50, 0)
    dur = timedelta(minutes=20)
    assert event_is_active(time(23, 55, 0), start, dur)
    assert event_is_active(time(0, 5, 0), start, dur)
    assert not event_is_active(time(0, 10, 0), start, dur)
    assert not event_is_active(time(23, 49, 0), start, dur)


def test_overlap_detects_wrap():
    a = (time(23, 50), timedelta(minutes=20))
    b = (time(0, 5), timedelta(minutes=10))
    assert windows_overlap(*a, *b)
    c = (time(8, 0), timedelta(minutes=5))
    d = (time(8, 10), timedelta(minutes=5))
    assert not windows_overlap(*c, *d)


def test_whatnow_event_beats_schedule():
    now = datetime(2026, 9, 16, 8, 3, 0)
    events = [EventLike(time(8, 0), timedelta(minutes=5), IMG)]
    schedule = [ScheduleLike(datetime(2026, 9, 16, 7, 0, 0), VID)]
    out = resolve_now(now, events, schedule)
    assert out == {"type": "image", "path": "media/1.jpg"}


def test_whatnow_schedule_sticky_until_next_or_midnight():
    now = datetime(2026, 9, 16, 15, 0, 0)
    schedule = [
        ScheduleLike(datetime(2026, 9, 16, 8, 0, 0), IMG),
        ScheduleLike(datetime(2026, 9, 16, 12, 0, 0), VID),
    ]
    out = resolve_now(now, [], schedule)
    assert out == {"type": "video", "path": "media/8.mp4"}


def test_whatnow_schedule_does_not_cross_midnight():
    now = datetime(2026, 9, 17, 0, 5, 0)
    schedule = [ScheduleLike(datetime(2026, 9, 16, 23, 0, 0), VID)]
    out = resolve_now(now, [], schedule)
    assert out == {"type": "image", "path": "media/default.jpg"}


def test_whatnow_skips_unready_media():
    now = datetime(2026, 9, 16, 8, 3, 0)
    events = [EventLike(time(8, 0), timedelta(minutes=5), NOT_READY)]
    out = resolve_now(now, events, [])
    assert out["path"] == "media/default.jpg"


def test_whatnow_latest_active_event_wins():
    now = datetime(2026, 9, 16, 8, 3, 0)
    events = [
        EventLike(time(8, 0), timedelta(minutes=10), IMG),
        EventLike(time(8, 2), timedelta(minutes=5), VID),
    ]
    out = resolve_now(now, events, [])
    assert out == {"type": "video", "path": "media/8.mp4"}


def test_window_from_range_short():
    dur, eod = window_from_range(time(9, 0), time(9, 3))
    assert dur == timedelta(minutes=3)
    assert eod is False
    assert end_clock(time(9, 0), dur, eod) == time(9, 3)


def test_window_from_range_eod():
    dur, eod = window_from_range(time(19, 0), time(23, 59))
    assert eod is True
    assert end_clock(time(19, 0), dur, eod) == time(23, 59)


def test_window_from_range_rejects_equal():
    try:
        window_from_range(time(8, 0), time(8, 0))
    except DurationError:
        return
    raise AssertionError("should reject")


def test_until_midnight_holds_past_duration():
    """LOGO з 19:00 до кінця доби не віддає ранковий слот о 23:30."""
    now = datetime(2026, 9, 16, 23, 30, 0)
    events = [
        EventLike(time(19, 0), timedelta(hours=4), IMG, until_midnight=True),
    ]
    schedule = [ScheduleLike(datetime(2026, 9, 16, 8, 0, 0), VID)]
    out = resolve_now(now, events, schedule)
    assert out == {"type": "image", "path": "media/1.jpg"}


def test_until_midnight_releases_after_midnight():
    now = datetime(2026, 9, 17, 0, 5, 0)
    events = [
        EventLike(time(19, 0), timedelta(hours=5), IMG, until_midnight=True),
    ]
    schedule = [ScheduleLike(datetime(2026, 9, 16, 8, 0, 0), VID)]
    out = resolve_now(now, events, schedule)
    assert out == {"type": "image", "path": "media/default.jpg"}


def test_without_flag_long_event_returns_to_schedule():
    now = datetime(2026, 9, 16, 23, 30, 0)
    events = [EventLike(time(19, 0), timedelta(hours=4), IMG, until_midnight=False)]
    schedule = [ScheduleLike(datetime(2026, 9, 16, 8, 0, 0), VID)]
    out = resolve_now(now, events, schedule)
    assert out == {"type": "video", "path": "media/8.mp4"}


def test_air_path_has_no_leading_slash():
    now = datetime(2026, 9, 16, 8, 3, 0)
    events = [EventLike(time(8, 0), timedelta(minutes=5), VID)]
    out = resolve_now(now, events, [])
    assert not out["path"].startswith("/")
    assert out["path"].startswith("media/")
