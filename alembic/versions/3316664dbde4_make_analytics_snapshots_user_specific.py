"""make analytics snapshots user specific

Revision ID: 3316664dbde4
Revises: 2874adc34f32
Create Date: 2026-10-29 14:48:39.158816

"""
from typing import Sequence, Union
from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3316664dbde4'
down_revision: Union[str, Sequence[str], None] = '2874adc34f32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("analytics_snapshot")

    op.create_table(
        "analytics_snapshot",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )

def downgrade() -> None:
    op.drop_table("analytics_snapshot")

    op.create_table(
        "analytics_snapshot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
