"""Add UNIQUE constraint on analysis_results_cache(analysis_type, upload_job_id)

Revision ID: b9e2f1a3c8d7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-23

Without this unique constraint, the ON CONFLICT (analysis_type, upload_job_id)
clause in the analytics upsert helper (_base.py) raises:
  ERROR: there is no unique or exclusion constraint matching the ON CONFLICT specification

This meant ALL 22 analytics module results could never be stored.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers
revision: str = "b9e2f1a3c8d7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add UNIQUE index on analysis_results_cache(analysis_type, upload_job_id)."""
    op.create_index(
        "ix_arc_analysis_type_job_unique",
        "analysis_results_cache",
        ["analysis_type", "upload_job_id"],
        unique=True,
    )


def downgrade() -> None:
    """Remove the unique index."""
    op.drop_index(
        "ix_arc_analysis_type_job_unique",
        table_name="analysis_results_cache",
    )
