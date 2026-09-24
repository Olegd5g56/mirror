"""Обробка щойно залитого файлу: mime, jpeg/mp4, thumb, постер.

Результат пишеться в temp/{id}.work.* і з'являється в air/ лише атомарним
перейменуванням під FOR UPDATE рядка. Якщо рядок уже видалили, публічного
файлу не з'являється і задачу не ретраїмо. Incoming знімаємо після commit.
Якщо воркер помер — acks_late + recover на старті переставлять задачу в чергу.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import time
from pathlib import Path

import magic
from celery.signals import worker_ready
from PIL import Image
from sqlalchemy import select

from app.config import settings
from app.enums import MediaStatus, MediaType
from app.models import Media
from app.services.media_files import (
    air_paths,
    incoming_path,
    remove_artifacts,
    start_action,
    stop_process,
    work_image_path,
    work_poster_path,
    work_thumb_path,
    work_video_path,
)
from app.tasks.celery_app import celery_app
from app.tasks.db_worker import session_scope

log = logging.getLogger(__name__)
MEDIA_ROOT = Path(settings.media_root)
THUMB_MAX_SIDE = 400

ALLOWED_MIME = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "video/mp4",
    "video/webm",
    "video/quicktime",
}


class PermanentMediaError(Exception):
    """Немає сенсу ретраїти (битий MIME тощо)."""


class MediaGone(Exception):
    """Рядок медіа видалили, поки файл ще оброблявся."""


def _make_thumbnail(src: Path, dst: Path, max_side: int = THUMB_MAX_SIDE) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = im.convert("RGB")
        im.thumbnail((max_side, max_side))
        im.save(dst, "WEBP", quality=85, method=4)


def _convert_to_jpg(src: Path, dst: Path) -> tuple[int, int]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img.convert("RGBA"), mask=img.convert("RGBA").getchannel("A"))
            background.save(dst, "JPEG", quality=90)
            return background.size
        rgb = img.convert("RGB")
        rgb.save(dst, "JPEG", quality=90)
        return rgb.size


def _ffprobe(path: Path) -> dict:
    res = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(path),
        ],
        check=True, capture_output=True, text=True,
    )
    return json.loads(res.stdout)


def _has_audio(info: dict) -> bool:
    return any(s.get("codec_type") == "audio" for s in info.get("streams") or [])


def _video_already_ok(info: dict) -> bool:
    fmt = (info.get("format") or {}).get("format_name") or ""
    if "mp4" not in fmt.split(","):
        return False
    vcodec, acodec = None, None
    for stream in info.get("streams") or []:
        if stream.get("codec_type") == "video" and vcodec is None:
            vcodec = stream.get("codec_name")
        elif stream.get("codec_type") == "audio" and acodec is None:
            acodec = stream.get("codec_name")
    return vcodec == "h264" and acodec in ("aac", None)


def _make_video_poster(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(src),
            "-frames:v", "1",
            "-q:v", "3",
            str(dst),
        ],
        check=True, capture_output=True,
    )


def _convert_video(
    src: Path,
    dst: Path,
    on_progress=None,
    has_audio: bool = True,
    stop_check=None,
) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    info = _ffprobe(src)
    try:
        duration = float(info["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        duration = 0.0

    cmd = [
        "ffmpeg", "-i", str(src),
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "veryfast",
    ]
    if has_audio:
        cmd += ["-c:a", "aac"]
    else:
        cmd += ["-an"]
    cmd += [
        "-movflags", "+faststart",
        "-y", str(dst),
        "-progress", "pipe:1", "-nostats",
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    try:
        stopped = False
        for line in process.stdout:
            if stop_check is not None and stop_check():
                stopped = True
                break
            line = line.strip()
            if line.startswith("out_time_ms=") and duration > 0 and on_progress:
                value = line.split("=", 1)[1]
                if value != "N/A":
                    ms = int(value)
                    progress = min((ms / (duration * 1_000_000)) * 100, 100.0)
                    on_progress(int(progress))
        if stopped:
            raise MediaGone()
        rc = process.wait()
        if rc != 0:
            raise RuntimeError(f"ffmpeg exited {rc}")
    finally:
        if process.poll() is None:
            process.stdout.close()
            stop_process(process)


def _copy_file(src: Path, dst: Path, stop_check=None) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("rb") as src_f, dst.open("wb") as dst_f:
        while True:
            if stop_check is not None and stop_check():
                raise MediaGone()
            chunk = src_f.read(8 * 1024 * 1024)
            if not chunk:
                break
            dst_f.write(chunk)


def _jpeg_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as im:
        return im.size


async def _set_status(media_id: int, status: str, progress: int | None = None) -> None:
    async with session_scope() as session:
        media = await session.get(Media, media_id)
        if media is None:
            return
        if media.status == MediaStatus.ready.value and status != MediaStatus.ready.value:
            return
        media.status = status
        if progress is not None:
            media.progress = progress
        await session.commit()


async def _row_state(media_id: int) -> tuple[bool, bool]:
    """(рядок є, уже ready). Статус знімаємо всередині сесії — після close він detached."""
    async with session_scope() as session:
        media = await session.get(Media, media_id)
        if media is None:
            return False, False
        return True, media.status == MediaStatus.ready.value


def _air_ready(media_id: int) -> bool:
    return any(path.exists() for path in air_paths(MEDIA_ROOT, media_id))


async def _fail_and_cleanup(media_id: int) -> None:
    async with session_scope() as session:
        media = await session.get(Media, media_id)
        if media is not None and media.status == MediaStatus.ready.value:
            return
        if media is not None:
            media.status = MediaStatus.failed.value
            await session.commit()
    remove_artifacts(MEDIA_ROOT, media_id)


async def _mark_processing(media_id: int, status: str, progress: int | None = None) -> None:
    async with session_scope() as session:
        media = await session.get(Media, media_id)
        if media is None:
            raise MediaGone()
        if media.status == MediaStatus.ready.value:
            return
        media.status = status
        if progress is not None:
            media.progress = progress
        await session.commit()


def _stop_checker(media_id: int):
    """Раз на секунду дивиться, чи рядок ще живий. Виклик із потоку ffmpeg."""
    state = {"at": 0.0, "gone": False}

    def check() -> bool:
        if state["gone"]:
            return True
        now = time.monotonic()
        if now - state["at"] < 1.0:
            return False
        state["at"] = now
        state["gone"] = asyncio.run(_row_missing(media_id))
        return state["gone"]

    return check


async def _row_missing(media_id: int) -> bool:
    async with session_scope() as session:
        return await session.get(Media, media_id) is None


def _replace_into(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.replace(dst)
    return True


async def _publish(
    media_id: int,
    *,
    kind: str,
    mime: str,
    width: int | None,
    height: int | None,
    duration_sec: int | None,
) -> None:
    """Перейменувати work → air під блокуванням рядка. Немає рядка — нічого не публікуємо."""
    async with session_scope() as session:
        media = await session.get(Media, media_id, with_for_update=True)
        if media is None:
            raise MediaGone()
        if kind == "image":
            published = _replace_into(
                work_image_path(MEDIA_ROOT, media_id),
                MEDIA_ROOT / "air" / f"{media_id}.jpg",
            )
        else:
            published = _replace_into(
                work_video_path(MEDIA_ROOT, media_id),
                MEDIA_ROOT / "air" / f"{media_id}.mp4",
            )
        if not published:
            raise RuntimeError(f"work file missing {media_id}")
        has_thumb = _replace_into(
            work_thumb_path(MEDIA_ROOT, media_id),
            MEDIA_ROOT / "thumbs" / f"{media_id}.webp",
        )
        has_poster = kind == "video" and _replace_into(
            work_poster_path(MEDIA_ROOT, media_id),
            MEDIA_ROOT / "posters" / f"{media_id}.jpg",
        )
        media.type = MediaType.video.value if kind == "video" else MediaType.image.value
        media.mime_type = mime
        media.status = MediaStatus.ready.value
        media.progress = 100
        media.width = width
        media.height = height
        media.duration_sec = duration_sec
        media.thumb_path = f"thumbs/{media_id}.webp" if has_thumb else None
        media.poster_path = f"posters/{media_id}.jpg" if has_poster else None
        await session.commit()
    remove_artifacts(MEDIA_ROOT, media_id, public=False, work=False, incoming=True)


async def _process_async(media_id: int) -> None:
    incoming = incoming_path(MEDIA_ROOT, media_id)
    row_exists, ready = await _row_state(media_id)
    action = start_action(
        row_exists=row_exists,
        ready=ready,
        incoming=incoming.exists(),
        air=_air_ready(media_id),
    )
    if action == "cancel":
        log.info("process_media cancelled id=%s", media_id)
        remove_artifacts(MEDIA_ROOT, media_id)
        raise MediaGone()
    if action == "done":
        remove_artifacts(MEDIA_ROOT, media_id, public=False)
        log.info("process_media id=%s: already ready", media_id)
        return
    if action == "mark_ready":
        log.info("process_media id=%s: incoming gone, air exists — ready", media_id)
        await _set_status(media_id, MediaStatus.ready.value, 100)
        return
    if action == "fail":
        log.error("process_media: incoming missing %s", incoming)
        await _fail_and_cleanup(media_id)
        raise PermanentMediaError(f"incoming missing {media_id}")

    stop_check = _stop_checker(media_id)
    try:
        await _mark_processing(media_id, MediaStatus.processing.value)
        mime = magic.from_file(str(incoming), mime=True) or ""
        if mime == "image/jpg":
            mime = "image/jpeg"
        if mime not in ALLOWED_MIME:
            raise PermanentMediaError(f"unsupported mime {mime}")

        kind = "video" if mime.startswith("video/") else "image"
        width = height = duration_sec = None
        work_thumb = work_thumb_path(MEDIA_ROOT, media_id)

        if kind == "image":
            dest = work_image_path(MEDIA_ROOT, media_id)
            if mime == "image/jpeg":
                await asyncio.to_thread(_copy_file, incoming, dest, stop_check)
                width, height = await asyncio.to_thread(_jpeg_size, dest)
            else:
                width, height = await asyncio.to_thread(_convert_to_jpg, incoming, dest)
            await asyncio.to_thread(_make_thumbnail, dest, work_thumb)
        else:
            info = await asyncio.to_thread(_ffprobe, incoming)
            for stream in info.get("streams") or []:
                if stream.get("codec_type") == "video":
                    width = stream.get("width")
                    height = stream.get("height")
                    break
            try:
                duration_sec = int(float(info["format"]["duration"]))
            except (KeyError, TypeError, ValueError):
                duration_sec = None

            dest = work_video_path(MEDIA_ROOT, media_id)
            if _video_already_ok(info):
                await asyncio.to_thread(_copy_file, incoming, dest, stop_check)
            else:
                await _mark_processing(media_id, MediaStatus.converting.value, 0)
                last = {"p": -1}

                def on_progress_sync(p: int) -> None:
                    if p - last["p"] < 5 and p < 100:
                        return
                    last["p"] = p
                    _progress_sync(media_id, p)

                await asyncio.to_thread(
                    _convert_video,
                    incoming,
                    dest,
                    on_progress_sync,
                    _has_audio(info),
                    stop_check,
                )

            try:
                poster = work_poster_path(MEDIA_ROOT, media_id)
                await asyncio.to_thread(_make_video_poster, dest, poster)
                await asyncio.to_thread(_make_thumbnail, poster, work_thumb)
            except MediaGone:
                raise
            except Exception as e:  # noqa: BLE001
                log.warning("poster/thumb failed id=%s: %s", media_id, e)

        await _publish(
            media_id,
            kind=kind,
            mime=mime,
            width=width,
            height=height,
            duration_sec=duration_sec,
        )
        log.info("processed media id=%s type=%s mime=%s", media_id, kind, mime)
    except MediaGone:
        log.info("process_media cancelled id=%s", media_id)
        remove_artifacts(MEDIA_ROOT, media_id)
        raise
    except PermanentMediaError:
        await _fail_and_cleanup(media_id)
        raise
    except Exception:
        # Incoming лишається — retry / recover підхопить. Work-файли не публічні.
        remove_artifacts(MEDIA_ROOT, media_id, public=False, incoming=False)
        log.exception("process_media failed id=%s (will retry)", media_id)
        raise


def _progress_sync(media_id: int, progress: int) -> None:
    asyncio.run(_set_status(media_id, MediaStatus.converting.value, progress))


@celery_app.task(
    bind=True,
    name="mirror.media.process_media",
    max_retries=3,
    acks_late=True,
)
def process_media(self, media_id: int) -> None:
    try:
        asyncio.run(_process_async(media_id))
    except (PermanentMediaError, MediaGone):
        return
    except Exception as exc:
        if self.request.retries >= (self.max_retries or 3):
            asyncio.run(_fail_and_cleanup(media_id))
            raise
        countdown = min(5 * (2 ** self.request.retries), 60)
        raise self.retry(exc=exc, countdown=countdown) from exc


async def _recover_stuck() -> None:
    stuck = (MediaStatus.pending.value, MediaStatus.processing.value, MediaStatus.converting.value)
    async with session_scope() as session:
        rows = (
            await session.execute(select(Media).where(Media.status.in_(stuck)))
        ).scalars().all()
        ids = [m.id for m in rows]
    for mid in ids:
        incoming = incoming_path(MEDIA_ROOT, mid)
        if incoming.exists():
            log.warning("recover: requeue media id=%s", mid)
            process_media.delay(mid)
        elif _air_ready(mid):
            await _set_status(mid, MediaStatus.ready.value, 100)
            log.warning("recover: air exists, mark ready id=%s", mid)
        else:
            await _set_status(mid, MediaStatus.failed.value)
            log.warning("recover: no incoming/air, mark failed id=%s", mid)


@worker_ready.connect
def recover_stuck_media(**_kwargs) -> None:
    try:
        asyncio.run(_recover_stuck())
    except Exception:
        log.exception("recover_stuck_media failed")
