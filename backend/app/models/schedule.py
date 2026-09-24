from datetime import datetime

from sqlalchemy import ForeignKey, Integer, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.media import Media


class Schedule(Base):
    __tablename__ = "schedule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    media_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("media.id", ondelete="RESTRICT"),
        nullable=False,
    )
    start_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), unique=True, nullable=False
    )

    media: Mapped[Media] = relationship(back_populates="schedule_items")
