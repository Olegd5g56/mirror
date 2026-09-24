"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("username", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "media",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("progress", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("thumb_path", sa.Text(), nullable=True),
        sa.Column("poster_path", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.CheckConstraint("type IN ('image', 'video')", name="ck_media_type"),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'converting', 'ready', 'failed')",
            name="ck_media_status",
        ),
        sa.CheckConstraint("progress BETWEEN 0 AND 100", name="ck_media_progress"),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("start_at", sa.Time(), nullable=False, unique=True),
        sa.Column("duration", sa.Interval(), nullable=False),
        sa.Column(
            "media_id",
            sa.Integer(),
            sa.ForeignKey("media.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "duration > INTERVAL '0 seconds' AND duration < INTERVAL '1 hour'",
            name="ck_events_duration",
        ),
    )

    op.create_table(
        "schedule",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "media_id",
            sa.Integer(),
            sa.ForeignKey("media.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("start_at", sa.TIMESTAMP(timezone=True), nullable=False, unique=True),
    )
    op.create_index("ix_schedule_start_at", "schedule", ["start_at"])


def downgrade() -> None:
    op.drop_table("schedule")
    op.drop_table("events")
    op.drop_table("media")
    op.drop_table("users")
