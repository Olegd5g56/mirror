from datetime import time

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.now import DurationError, end_clock, format_mmss, window_from_range


class EventCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    start_at: time
    end_at: time
    media_id: int

    @model_validator(mode="after")
    def valid_window(self) -> "EventCreate":
        try:
            window_from_range(self.start_at, self.end_at)
        except DurationError as e:
            raise ValueError(str(e)) from e
        return self


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    start_at: time
    end_at: time
    duration: str
    until_midnight: bool
    media_id: int
    media_name: str

    @classmethod
    def from_row(cls, row) -> "EventOut":
        return cls(
            id=row.id,
            name=row.name,
            start_at=row.start_at,
            end_at=end_clock(row.start_at, row.duration, bool(row.until_midnight)),
            duration=format_mmss(row.duration),
            until_midnight=bool(row.until_midnight),
            media_id=row.media_id,
            media_name=row.media.name if row.media is not None else "",
        )
