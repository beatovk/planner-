"""drop_fts5_table_and_triggers

Revision ID: 6c51662cda39
Revises: e9eea0b88af9
Create Date: 2025-09-05 20:47:45.196384

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c51662cda39'
down_revision: Union[str, Sequence[str], None] = 'e9eea0b88af9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop FTS5 triggers first
    op.execute("DROP TRIGGER IF EXISTS fts_places_ai;")
    op.execute("DROP TRIGGER IF EXISTS fts_places_au;")
    op.execute("DROP TRIGGER IF EXISTS fts_places_ad;")
    
    # Drop FTS5 table and all related tables
    op.execute("DROP TABLE IF EXISTS fts_places;")
    op.execute("DROP TABLE IF EXISTS fts_places_data;")
    op.execute("DROP TABLE IF EXISTS fts_places_idx;")
    op.execute("DROP TABLE IF EXISTS fts_places_config;")
    op.execute("DROP TABLE IF EXISTS fts_places_docsize;")
    op.execute("DROP TABLE IF EXISTS fts_places_content;")


def downgrade() -> None:
    """Downgrade schema."""
    # Recreate FTS5 table (this will be done in next migration)
    pass
