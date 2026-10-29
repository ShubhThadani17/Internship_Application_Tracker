"""add deadline notification queued timestamp

Revision ID: e870414c35b0
Revises: 2e840896b2a8
Create Date: 2026-10-29 16:25:04.142628

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e870414c35b0'
down_revision: Union[str, Sequence[str], None] = '2e840896b2a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column(
            "deadline_notification_queued_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "applications",
        "deadline_notification_queued_at",
    )
