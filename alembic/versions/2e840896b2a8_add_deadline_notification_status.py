"""add deadline notification status

Revision ID: 2e840896b2a8
Revises: 3316664dbde4
Create Date: 2026-10-29 16:01:35.268390

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2e840896b2a8'
down_revision: Union[str, Sequence[str], None] = '3316664dbde4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column(
            "deadline_notification_status",
            sa.String(length=16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "applications",
        "deadline_notification_status",
    )   
