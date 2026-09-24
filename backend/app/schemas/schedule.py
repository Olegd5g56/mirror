from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScheduleCreate(BaseModel):
    media_id: int
    start_at: datetime = Field(description="Наївний час інтерпретується як Europe/Kyiv")


class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    media_id: int
    media_name: str
    start_at: datetime

    @classmethod
    def from_row(cls, row) -> "ScheduleOut":
        return cls(
            id=row.id,
            media_id=row.media_id,
            media_name=row.media.name if row.media is not None else "",
            start_at=row.start_at,
        )
