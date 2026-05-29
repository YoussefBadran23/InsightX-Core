"""add source_currency to upload_jobs

Adds a per-upload `source_currency` column to record the native currency of the
CSV's monetary values. Detected automatically in stage3 from the data's
`currency` column (mode), or set explicitly at upload time via an override.
Read by the frontend so values can be FX-converted to the user's preferred
display currency end-to-end.

Revision ID: c7d9a0e1f234
Revises: 89a2bcdef123
Create Date: 2026-05-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d9a0e1f234'
down_revision: Union[str, Sequence[str], None] = '89a2bcdef123'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable source_currency (3-letter ISO 4217); existing rows backfill to USD."""
    op.add_column(
        'upload_jobs',
        sa.Column('source_currency', sa.String(3), nullable=True),
    )
    # Backfill existing rows to 'USD' — the previous implicit assumption.
    op.execute("UPDATE upload_jobs SET source_currency = 'USD' WHERE source_currency IS NULL")


def downgrade() -> None:
    op.drop_column('upload_jobs', 'source_currency')
