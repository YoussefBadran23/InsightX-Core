"""add_csv_column_mappings

Revision ID: 68c6aa493887
Revises: bc64448bc4fe
Create Date: 2026-04-29 19:17:41.833930

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '68c6aa493887'
down_revision: Union[str, Sequence[str], None] = 'bc64448bc4fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'csv_column_mappings',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('upload_job_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('upload_jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('csv_header', sa.String(255), nullable=False),
        sa.Column('mapped_table', sa.String(100), nullable=False),
        sa.Column('mapped_column', sa.String(100), nullable=False),
        sa.Column('match_score', sa.Numeric(5, 4), nullable=False),
        sa.Column('match_method', sa.String(30), nullable=False, server_default='fuzzy'),
        sa.Column('is_confirmed', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('upload_job_id', 'csv_header', name='uq_csv_mapping_job_header'),
    )
    op.create_index('ix_csv_column_mappings_upload_job_id', 'csv_column_mappings', ['upload_job_id'])
    op.create_index('ix_csv_column_mappings_csv_header', 'csv_column_mappings', ['csv_header'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_csv_column_mappings_csv_header', table_name='csv_column_mappings')
    op.drop_index('ix_csv_column_mappings_upload_job_id', table_name='csv_column_mappings')
    op.drop_table('csv_column_mappings')
