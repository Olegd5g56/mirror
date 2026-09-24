from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str
    status: str
    progress: int
    mime_type: str
    size_bytes: int
    duration_sec: int | None
    width: int | None
    height: int | None
    thumb_url: str | None = None
    poster_url: str | None = None
    air_url: str | None = None
    created_at: datetime
    used_in_events: int = 0
    used_in_schedule: int = 0


def media_to_out(
    row,
    *,
    events_count: int = 0,
    schedule_count: int = 0,
) -> MediaOut:
    thumb = f"/media/thumbs/{row.id}.webp" if row.thumb_path else None
    poster = f"/media/posters/{row.id}.jpg" if row.poster_path else None
    air = None
    if row.status == "ready":
        ext = "mp4" if row.type == "video" else "jpg"
        air = f"/media/{row.id}.{ext}"
    return MediaOut(
        id=row.id,
        name=row.name,
        type=row.type,
        status=row.status,
        progress=row.progress,
        mime_type=row.mime_type,
        size_bytes=row.size_bytes,
        duration_sec=row.duration_sec,
        width=row.width,
        height=row.height,
        thumb_url=thumb,
        poster_url=poster,
        air_url=air,
        created_at=row.created_at,
        used_in_events=events_count,
        used_in_schedule=schedule_count,
    )


class MediaNameIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
