# add_is_segment_to_videos
"""add_is_segment_to_videos

Revision ID: e5f6a7b8c9d0
Revises: d4f5e6a7b8c9
Create Date: 2026-06-20 10:30:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4f5e6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply the migration."""
    op.add_column('videos', sa.Column('is_segment', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    """Revert the migration."""
    op.drop_column('videos', 'is_segment')
