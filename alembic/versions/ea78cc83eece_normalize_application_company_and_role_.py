"""normalize application company and role names

Revision ID: ea78cc83eece
Revises: e870414c35b0
Create Date: 2026-10-30 12:47:05.037099

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ea78cc83eece'
down_revision: Union[str, Sequence[str], None] = 'e870414c35b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE applications
        SET
            company_name = UPPER(
                REGEXP_REPLACE(
                    BTRIM(company_name),
                    '[[:space:]]+',
                    ' ',
                    'g'
                )
            ),
            role_title = LOWER(
                REGEXP_REPLACE(
                    BTRIM(role_title),
                    '[[:space:]]+',
                    ' ',
                    'g'
                )
            )
        """
    )


def downgrade() -> None:
    # Original capitalization and whitespace cannot be reconstructed.
    pass