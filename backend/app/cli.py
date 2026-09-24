"""CLI адміністратора.

    python -m app.cli create-user <username>
    python -m app.cli regen-thumbs [--missing-only]
    python -m app.cli vacuum-temp [--apply]
    python -m app.cli import-legacy --source-url ... --source-media ...
"""

from __future__ import annotations

import asyncio
import getpass
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import click
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.db import SessionLocal
from app.enums import MediaStatus, MediaType
from app.models import Event, Media, Schedule, User
from app.services.now import SECONDS_IN_DAY, time_to_sec
from app.services.security import hash_password

MEDIA_ROOT = Path(settings.media_root)
USERNAME_RE = re.compile(r"^[a-zA-Z0-9._-]{3,32}$")
MIN_PASSWORD_LEN = 8


@click.group()
def cli() -> None:
    """Mirror admin CLI."""


@cli.command("create-user")
@click.argument("username")
def create_user_cmd(username: str) -> None:
    """Створити користувача. Пароль читається зі stdin."""
    if not USERNAME_RE.match(username):
        click.echo(
            "Ім'я: латиниця, цифри, крапка/тире/підкреслення, 3–32 символи.",
            err=True,
        )
        sys.exit(2)

    if sys.stdin.isatty():
        password = getpass.getpass("Пароль: ")
        password_confirm = getpass.getpass("Повторіть пароль: ")
        if password != password_confirm:
            click.echo("Паролі не збігаються.", err=True)
            sys.exit(2)
    else:
        password = sys.stdin.readline().rstrip("\n")

    if len(password) < MIN_PASSWORD_LEN:
        click.echo(f"Пароль має бути мінімум {MIN_PASSWORD_LEN} символів.", err=True)
        sys.exit(2)

    asyncio.run(_create_user(username, password))


async def _create_user(username: str, password: str) -> None:
    async with SessionLocal() as session:
        user = User(username=username, password_hash=hash_password(password))
        session.add(user)
        try:
            await session.commit()
        except IntegrityError:
            click.echo(f"Користувач '{username}' уже існує.", err=True)
            sys.exit(1)
        await session.refresh(user)
        click.echo(f"Створено {user.username} (id={user.id})")


@cli.command("regen-thumbs")
@click.option("--missing-only", is_flag=True)
def regen_thumbs_cmd(missing_only: bool) -> None:
    asyncio.run(_regen_thumbs(missing_only))


async def _regen_thumbs(missing_only: bool) -> None:
    from app.tasks.media_processing import _make_thumbnail, _make_video_poster

    async with SessionLocal() as session:
        rows = (await session.execute(select(Media))).scalars().all()
        done = skipped = failed = 0
        for m in rows:
            thumb_abs = MEDIA_ROOT / "thumbs" / f"{m.id}.webp"
            if missing_only and m.thumb_path and thumb_abs.exists():
                skipped += 1
                continue
            src = MEDIA_ROOT / "air" / (
                f"{m.id}.mp4" if m.type == MediaType.video.value else f"{m.id}.jpg"
            )
            if not src.exists():
                click.echo(f"[skip] {m.id} air missing", err=True)
                failed += 1
                continue
            try:
                if m.type == MediaType.video.value:
                    poster = MEDIA_ROOT / "posters" / f"{m.id}.jpg"
                    _make_video_poster(src, poster)
                    _make_thumbnail(poster, thumb_abs)
                    m.poster_path = f"posters/{m.id}.jpg"
                else:
                    _make_thumbnail(src, thumb_abs)
                m.thumb_path = f"thumbs/{m.id}.webp"
                done += 1
            except Exception as e:  # noqa: BLE001
                click.echo(f"[fail] {m.id}: {e}", err=True)
                failed += 1
        await session.commit()
    click.echo(f"done={done} skipped={skipped} failed={failed}")


@cli.command("vacuum-temp")
@click.option("--older-than-hours", type=int, default=48)
@click.option("--apply", is_flag=True)
def vacuum_temp_cmd(older_than_hours: int, apply: bool) -> None:
    temp_dir = MEDIA_ROOT / "temp"
    if not temp_dir.exists():
        click.echo("/media/temp не існує")
        return
    cutoff = time.time() - older_than_hours * 3600
    candidates = [
        p
        for p in temp_dir.iterdir()
        if p.is_file() and not p.name.startswith(".") and p.stat().st_mtime < cutoff
    ]
    click.echo(f"знайдено {len(candidates)} файлів старше {older_than_hours}h")
    if not apply:
        for p in candidates[:50]:
            click.echo(f"  {p.name}")
        if candidates:
            click.echo("DRY-RUN: --apply щоб видалити")
        return
    removed = 0
    for p in candidates:
        try:
            p.unlink()
            removed += 1
        except OSError as e:
            click.echo(f"[fail] {p.name}: {e}", err=True)
    click.echo(f"видалено: {removed}")


@cli.command("import-legacy")
@click.option("--source-url", required=True, help="postgresql://mirror:pass@host:5432/mirror")
@click.option("--source-media", required=True, type=click.Path(exists=True, file_okay=False))
def import_legacy_cmd(source_url: str, source_media: str) -> None:
    """Перенести users/media/events/schedule зі старого Mirror, зберігши id."""
    asyncio.run(_import_legacy(source_url, Path(source_media)))


async def _import_legacy(source_url: str, source_media: Path) -> None:
    import psycopg

    kyiv = ZoneInfo(settings.tz)
    src = source_url.replace("postgresql+asyncpg://", "postgresql://")

    with psycopg.connect(src) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT login, password_hash FROM users")
            users = cur.fetchall()
            cur.execute("SELECT id, name, type FROM media ORDER BY id")
            media_rows = cur.fetchall()
            cur.execute("SELECT id, name, start_at, duration, media_id FROM events ORDER BY id")
            events = cur.fetchall()
            cur.execute("SELECT id, media_id, start_at FROM schedule ORDER BY id")
            schedule = cur.fetchall()

    async with SessionLocal() as session:
        existing_admin = (await session.execute(select(User))).scalars().first()
        if existing_admin is None:
            click.echo("Спочатку створи адміна: python -m app.cli create-user admin", err=True)
            sys.exit(1)
        uploader = existing_admin.id

        for login, password_hash in users:
            if login == existing_admin.username:
                continue
            session.add(User(username=login, password_hash=password_hash))
        await session.commit()

        air = MEDIA_ROOT / "air"
        air.mkdir(parents=True, exist_ok=True)
        copied = 0
        existing_media = set(
            (await session.execute(select(Media.id))).scalars().all()
        )
        for mid, name, mtype in media_rows:
            ext = "mp4" if mtype == "video" else "jpg"
            src_file = source_media / f"{mid}.{ext}"
            dst_file = air / f"{mid}.{ext}"
            size = 0
            ready = src_file.exists()
            if ready:
                shutil.copy2(src_file, dst_file)
                size = dst_file.stat().st_size
                copied += 1
            if mid in existing_media:
                continue
            session.add(
                Media(
                    id=mid,
                    name=name,
                    type=mtype if mtype in ("image", "video") else "image",
                    status=MediaStatus.ready.value if ready else MediaStatus.failed.value,
                    progress=100 if ready else 0,
                    mime_type="video/mp4" if mtype == "video" else "image/jpeg",
                    size_bytes=size,
                    uploaded_by=uploader,
                )
            )
        await session.commit()
        await session.execute(
            text("SELECT setval('media_id_seq', COALESCE((SELECT MAX(id) FROM media), 1))")
        )

        existing_events = set(
            (await session.execute(select(Event.id))).scalars().all()
        )
        for eid, name, start_at, duration, media_id in events:
            if eid in existing_events:
                continue
            end_s = time_to_sec(start_at) + int(duration.total_seconds())
            until_md = end_s <= SECONDS_IN_DAY and end_s >= 23 * 3600
            session.add(
                Event(
                    id=eid,
                    name=name,
                    start_at=start_at,
                    duration=duration,
                    until_midnight=until_md or name == "LOGO",
                    media_id=media_id,
                )
            )
        await session.commit()
        await session.execute(
            text("SELECT setval('events_id_seq', COALESCE((SELECT MAX(id) FROM events), 1))")
        )

        existing_sched = set(
            (await session.execute(select(Schedule.id))).scalars().all()
        )
        for sid, media_id, start_at in schedule:
            if sid in existing_sched:
                continue
            dt = start_at
            if isinstance(dt, datetime) and dt.tzinfo is None:
                dt = dt.replace(tzinfo=kyiv)
            session.add(Schedule(id=sid, media_id=media_id, start_at=dt))
        await session.commit()
        await session.execute(
            text("SELECT setval('schedule_id_seq', COALESCE((SELECT MAX(id) FROM schedule), 1))")
        )
        await session.commit()

    click.echo(
        f"імпортовано media={len(media_rows)} (файлів {copied}), "
        f"events={len(events)}, schedule={len(schedule)}"
    )
    click.echo("запусти regen-thumbs, щоб порахувати прев'ю")


if __name__ == "__main__":
    cli()
