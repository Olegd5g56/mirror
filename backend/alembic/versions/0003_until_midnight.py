"""Daily events can hold until midnight (LOGO from 19:00).

Revision ID: 0003
Revises: 0002
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column(
            "until_midnight",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    # Старий хак: LOGO з 19:00 на 4 години. Малось на увазі «з вечора до кінця доби».
    op.execute("UPDATE events SET until_midnight = true WHERE name = 'LOGO'")


def downgrade() -> None:
    op.drop_column("events", "until_midnight")
