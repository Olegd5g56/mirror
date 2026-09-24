"""Allow daily events up to 24h (prod has LOGO = 4 hours).

Revision ID: 0002
Revises: 0001
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_events_duration", "events", type_="check")
    op.create_check_constraint(
        "ck_events_duration",
        "events",
        "duration > INTERVAL '0 seconds' AND duration < INTERVAL '24 hours'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_events_duration", "events", type_="check")
    op.create_check_constraint(
        "ck_events_duration",
        "events",
        "duration > INTERVAL '0 seconds' AND duration < INTERVAL '1 hour'",
    )
