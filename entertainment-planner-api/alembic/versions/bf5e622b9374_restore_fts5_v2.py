"""restore_fts5_v2

Revision ID: bf5e622b9374
Revises: add_interest_signals_field
Create Date: 2025-09-17 10:44:49.362953

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bf5e622b9374'
down_revision: Union[str, Sequence[str], None] = 'add_interest_signals_field'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1) Виртуальная таблица FTS5 c внешним контентом = places
    op.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS fts_places USING fts5(
        name,               -- 1
        tags_csv,           -- 2
        summary,            -- 3
        category,           -- 4
        description_full,   -- 5
        address,            -- 6
        content='places',
        content_rowid='id',
        tokenize='unicode61 remove_diacritics 1 tokenchars "-"'
    );
    """)

    # 2) Триггеры синхронизации (insert/update/delete)
    op.execute("""
    CREATE TRIGGER IF NOT EXISTS places_ai AFTER INSERT ON places BEGIN
        INSERT INTO fts_places(rowid, name, tags_csv, summary, category, description_full, address)
        VALUES (new.id, new.name, new.tags_csv, new.summary, new.category, new.description_full, new.address);
    END;
    """)
    op.execute("""
    CREATE TRIGGER IF NOT EXISTS places_ad AFTER DELETE ON places BEGIN
        INSERT INTO fts_places(fts_places, rowid, name, tags_csv, summary, category, description_full, address)
        VALUES ('delete', old.id, old.name, old.tags_csv, old.summary, old.category, old.description_full, old.address);
    END;
    """)
    op.execute("""
    CREATE TRIGGER IF NOT EXISTS places_au AFTER UPDATE OF
        name, tags_csv, summary, category, description_full, address ON places BEGIN
        INSERT INTO fts_places(fts_places, rowid, name, tags_csv, summary, category, description_full, address)
        VALUES ('delete', old.id, old.name, old.tags_csv, old.summary, old.category, old.description_full, old.address);
        INSERT INTO fts_places(rowid, name, tags_csv, summary, category, description_full, address)
        VALUES (new.id, new.name, new.tags_csv, new.summary, new.category, new.description_full, new.address);
    END;
    """)

    # 3) Первичное заполнение FTS из контентной таблицы
    op.execute("INSERT INTO fts_places(fts_places) VALUES ('rebuild');")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS places_au;")
    op.execute("DROP TRIGGER IF EXISTS places_ad;")
    op.execute("DROP TRIGGER IF EXISTS places_ai;")
    op.execute("DROP TABLE IF EXISTS fts_places;")
