# add_transcript_text_to_videos
"""add_transcript_text_to_videos

Revision ID: a2c98d609aef
Revises: 73a7294f8f8b
Create Date: 2026-06-19 12:50:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2c98d609aef'
down_revision: Union[str, None] = '73a7294f8f8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply the migration."""
    op.add_column('videos', sa.Column('transcript_text', sa.Text(), nullable=True))


def downgrade() -> None:
    """Revert the migration."""
    op.drop_column('videos', 'transcript_text')
