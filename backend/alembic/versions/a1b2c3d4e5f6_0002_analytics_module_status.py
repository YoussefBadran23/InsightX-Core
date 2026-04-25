"""0002 — Add analytics_module_status table.

Tracks which of the 22 analytics modules can/cannot run per upload job,
based on which CSV columns the user's file contained.

Revision ID: a1b2c3d4e5f6
Revises: cd7f4376ca5f
Create Date: 2026-03-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "a1b2c3d4e5f6"
down_revision = "cd7f4376ca5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analytics_module_status",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "upload_job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("upload_jobs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("module_key", sa.String(60), nullable=False, index=True),
        sa.Column("module_name", sa.String(100), nullable=False),
        sa.Column("module_name_ar", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("can_run", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("queue", sa.String(20), nullable=False, server_default="analytics"),
        sa.Column("missing_required_columns", JSONB, nullable=True),
        sa.Column("missing_optional_columns", JSONB, nullable=True),
        sa.Column("run_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Unique constraint: one status row per (job, module)
    op.create_unique_constraint(
        "uq_module_status_job_module",
        "analytics_module_status",
        ["upload_job_id", "module_key"],
    )


def downgrade() -> None:
    op.drop_table("analytics_module_status")
