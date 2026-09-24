from datetime import time, timedelta

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Interval, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.media import Media


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            "duration > INTERVAL '0 seconds' AND duration < INTERVAL '24 hours'",
            name="ck_events_duration",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    start_at: Mapped[time] = mapped_column(Time, unique=True, nullable=False)
    duration: Mapped[timedelta] = mapped_column(Interval, nullable=False)
    until_midnight: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    media_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("media.id", ondelete="RESTRICT"),
        nullable=False,
    )

    media: Mapped[Media] = relationship(back_populates="events")
