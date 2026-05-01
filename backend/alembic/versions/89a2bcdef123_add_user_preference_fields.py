"""add user preference fields

Revision ID: 89a2bcdef123
Revises: 68c6aa493887
Create Date: 2026-04-30 20:02:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '89a2bcdef123'
down_revision: Union[str, Sequence[str], None] = '68c6aa493887'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('preferred_language', sa.String(10), nullable=True))
    op.add_column('users', sa.Column('preferred_theme', sa.String(20), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'preferred_theme')
    op.drop_column('users', 'preferred_language')
