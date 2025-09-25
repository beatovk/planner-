"""create_correct_fts5_table

Revision ID: 1e5d3814ad72
Revises: 6c51662cda39
Create Date: 2025-09-05 20:48:01.182992

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e5d3814ad72'
down_revision: Union[str, Sequence[str], None] = '6c51662cda39'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create FTS5 virtual table with external content and proper rowid
    op.execute("""
        CREATE VIRTUAL TABLE fts_places USING fts5(
            name,
            tags_csv,
            summary,
            category,
            description_full,
            address,
            content='places',
            content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
        );
    """)
    
    # Create trigger for INSERT
    op.execute("""
        CREATE TRIGGER fts_places_ai AFTER INSERT ON places BEGIN
            INSERT INTO fts_places(rowid, name, tags_csv, summary, category, description_full, address)
            VALUES (new.id, new.name, new.tags_csv, new.summary, new.category, new.description_full, new.address);
        END;
    """)
    
    # Create trigger for UPDATE
    op.execute("""
        CREATE TRIGGER fts_places_au AFTER UPDATE ON places BEGIN
            INSERT INTO fts_places(fts_places, rowid, name, tags_csv, summary, category, description_full, address)
            VALUES('delete', old.id, old.name, old.tags_csv, old.summary, old.category, old.description_full, old.address);
            INSERT INTO fts_places(rowid, name, tags_csv, summary, category, description_full, address)
            VALUES (new.id, new.name, new.tags_csv, new.summary, new.category, new.description_full, new.address);
        END;
    """)
    
    # Create trigger for DELETE
    op.execute("""
        CREATE TRIGGER fts_places_ad AFTER DELETE ON places BEGIN
            INSERT INTO fts_places(fts_places, rowid, name, tags_csv, summary, category, description_full, address)
            VALUES('delete', old.id, old.name, old.tags_csv, old.summary, old.category, old.description_full, old.address);
        END;
    """)
    
    # Populate FTS5 table with existing data
    op.execute("""
        INSERT INTO fts_places(rowid, name, tags_csv, summary, category, description_full, address)
        SELECT id, name, tags_csv, summary, category, description_full, address
        FROM places
        WHERE processing_status = 'summarized';
    """)
    
    # Optimize FTS5 index
    op.execute("""
        INSERT INTO fts_places(fts_places) VALUES('optimize');
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS fts_places_ai;")
    op.execute("DROP TRIGGER IF EXISTS fts_places_au;")
    op.execute("DROP TRIGGER IF EXISTS fts_places_ad;")
    
    # Drop FTS5 table
    op.execute("DROP TABLE IF EXISTS fts_places;")
