"""Add compound performance indexes for hot query paths.

Revision ID: d4e5f6a7b8c9
Revises: c7d9a0e1f234
Create Date: 2026-05-27
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c7d9a0e1f234'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # _resolve_latest_job() runs on every analytics/kpi/forecast page load.
    # Single-column indexes on user_id and status exist but force a sort on
    # completed_at. This compound index makes the query a single index scan.
    op.create_index(
        'ix_upload_jobs_user_status_completed',
        'upload_jobs',
        ['user_id', 'status', 'completed_at'],
        postgresql_ops={'completed_at': 'DESC NULLS LAST'},
    )

    # KPI summary fetches the latest snapshot ordered by snapshot_date.
    # Compound index eliminates the sort entirely.
    op.create_index(
        'ix_daily_kpi_user_date',
        'daily_kpi_snapshots',
        ['user_id', 'snapshot_date'],
        postgresql_ops={'snapshot_date': 'DESC'},
    )

    # analytics/summary fetches all 39 cache rows for a job ordered by type.
    # upload_job_id index already exists but adding analysis_type lets Postgres
    # satisfy the ORDER BY from the index without a separate sort step.
    op.create_index(
        'ix_arc_job_type',
        'analysis_results_cache',
        ['upload_job_id', 'analysis_type'],
    )


def downgrade() -> None:
    op.drop_index('ix_arc_job_type', table_name='analysis_results_cache')
    op.drop_index('ix_daily_kpi_user_date', table_name='daily_kpi_snapshots')
    op.drop_index('ix_upload_jobs_user_status_completed', table_name='upload_jobs')
