from __future__ import annotations

import asyncio
import os
from pathlib import Path


def extension_for(mime: str, filename: str) -> str:
    mime = (mime or "").lower()
    if mime in ("image/jpeg", "image/jpg"):
        return ".jpg"
    if mime == "image/png":
        return ".png"
    if mime == "image/webp":
        return ".webp"
    if mime == "video/mp4":
        return ".mp4"
    if mime == "video/webm":
        return ".webm"
    if mime == "video/quicktime":
        return ".mov"
    _, ext = os.path.splitext(filename or "")
    return ext.lower() or ".bin"


async def safe_unlink(path: Path) -> None:
    try:
        await asyncio.to_thread(path.unlink)
    except FileNotFoundError:
        return
    except OSError:
        return


async def move_into_storage(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(src.replace, dst)
