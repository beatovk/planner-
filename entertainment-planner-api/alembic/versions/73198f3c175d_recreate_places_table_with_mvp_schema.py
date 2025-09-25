"""Recreate places table with MVP schema

Revision ID: 73198f3c175d
Revises: c0f09b460eb6
Create Date: 2025-09-05 14:03:57.980020

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '73198f3c175d'
down_revision: Union[str, Sequence[str], None] = 'c0f09b460eb6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Создаем новую таблицу с правильной схемой
    op.create_table('places_new',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.Text(), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('raw_payload', sa.Text(), nullable=True),
        sa.Column('scraped_at', sa.DateTime(), nullable=True),
        sa.Column('lat', sa.Float(), nullable=True),
        sa.Column('lng', sa.Float(), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('gmaps_place_id', sa.Text(), nullable=True),
        sa.Column('gmaps_url', sa.Text(), nullable=True),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('category', sa.Text(), nullable=True),
        sa.Column('description_full', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('tags_csv', sa.Text(), nullable=True),
        sa.Column('price_level', sa.Integer(), nullable=True),
        sa.Column('hours_json', sa.Text(), nullable=True),
        sa.Column('processing_status', sa.Text(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_url')
    )
    
    # Копируем данные из старой таблицы в новую
    op.execute("""
        INSERT INTO places_new (
            id, source, source_url, raw_payload, scraped_at,
            lat, lng, name, category, tags_csv, summary,
            price_level, hours_json, processing_status, last_error,
            published_at, updated_at
        )
        SELECT 
            id, source, source_url, raw_payload, scraped_at,
            lat, lng, name, category, tags_csv, summary,
            price_level, hours_json, processing_status, last_error,
            published_at, updated_at
        FROM places
    """)
    
    # Удаляем старую таблицу
    op.drop_table('places')
    
    # Переименовываем новую таблицу
    op.rename_table('places_new', 'places')
    
    # Создаем индексы
    op.create_index(op.f('ix_places_id'), 'places', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Создаем старую таблицу
    op.create_table('places_old',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('raw_payload', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=64), nullable=True),
        sa.Column('source_url', sa.String(), nullable=True),
        sa.Column('scraped_at', sa.DateTime(), nullable=True),
        sa.Column('name', sa.String(length=256), nullable=True),
        sa.Column('category', sa.String(length=64), nullable=True),
        sa.Column('tags_csv', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('lat', sa.Float(), nullable=True),
        sa.Column('lng', sa.Float(), nullable=True),
        sa.Column('price_level', sa.Integer(), nullable=True),
        sa.Column('hours_json', sa.JSON(), nullable=True),
        sa.Column('processing_status', sa.String(length=16), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Копируем данные обратно
    op.execute("""
        INSERT INTO places_old (
            id, source, source_url, raw_payload, scraped_at,
            lat, lng, name, category, tags_csv, description, summary,
            price_level, hours_json, processing_status, last_error,
            published_at, updated_at
        )
        SELECT 
            id, source, source_url, raw_payload, scraped_at,
            lat, lng, name, category, tags_csv, description_full, summary,
            price_level, hours_json, processing_status, last_error,
            published_at, updated_at
        FROM places
    """)
    
    # Удаляем новую таблицу
    op.drop_table('places')
    
    # Переименовываем старую таблицу
    op.rename_table('places_old', 'places')
    
    # Создаем индексы
    op.create_index(op.f('ix_places_id'), 'places', ['id'], unique=False)
