from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Integer,
    SmallInteger,
    Text,
    TIMESTAMP,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.enums import MediaStatus, MediaType
from app.models.base import Base


class Media(Base):
    __tablename__ = "media"
    __table_args__ = (
        CheckConstraint(
            f"type IN ({', '.join(repr(t.value) for t in MediaType)})",
            name="ck_media_type",
        ),
        CheckConstraint(
            f"status IN ({', '.join(repr(s.value) for s in MediaStatus)})",
            name="ck_media_status",
        ),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_media_progress"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=MediaStatus.pending.value
    )
    progress: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumb_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    uploaded_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    events: Mapped[list["Event"]] = relationship(back_populates="media")  # noqa: F821
    schedule_items: Mapped[list["Schedule"]] = relationship(back_populates="media")  # noqa: F821
