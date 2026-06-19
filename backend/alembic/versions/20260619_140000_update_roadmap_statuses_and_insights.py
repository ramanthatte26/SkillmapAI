# update_roadmap_statuses_and_insights
"""update_roadmap_statuses_and_insights

Revision ID: b3d87e01acbc
Revises: a2c98d609aef
Create Date: 2026-06-19 14:00:00.000000+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3d87e01acbc'
down_revision: Union[str, None] = 'a2c98d609aef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply the migration."""
    # 1. Add insights_json column
    op.add_column('roadmaps', sa.Column('insights_json', sa.Text(), nullable=True))

    # 2. Add new values to roadmap_status_enum
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text("COMMIT"))
        for val in ['importing', 'generating_modules', 'generating_notes', 'building_search_index', 'ready', 'failed']:
            try:
                bind.execute(sa.text(f"ALTER TYPE roadmap_status_enum ADD VALUE '{val}'"))
            except Exception as e:
                # Ignore if the value already exists
                pass


def downgrade() -> None:
    """Revert the migration."""
    # 1. Drop column
    op.drop_column('roadmaps', 'insights_json')
    # Note: dropping enum values in PostgreSQL is not directly supported via ALTER TYPE. 
    # Since they won't conflict with older code, leaving them in the enum is standard and safe.
