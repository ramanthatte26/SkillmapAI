# add_module_time_fields
"""add_module_time_fields

Revision ID: d4f5e6a7b8c9
Revises: b3d87e01acbc
Create Date: 2026-06-19 17:15:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f5e6a7b8c9'
down_revision: Union[str, None] = 'b3d87e01acbc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply the migration."""
    op.add_column('modules', sa.Column('module_start_time', sa.Integer(), nullable=True))
    op.add_column('modules', sa.Column('module_youtube_url', sa.Text(), nullable=True))


def downgrade() -> None:
    """Revert the migration."""
    op.drop_column('modules', 'module_start_time')
    op.drop_column('modules', 'module_youtube_url')
