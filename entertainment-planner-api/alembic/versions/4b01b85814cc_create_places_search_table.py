"""create_places_search_table

Revision ID: 4b01b85814cc
Revises: 1ff394370c79
Create Date: 2025-09-26 20:02:24.667047

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b01b85814cc'
down_revision: Union[str, Sequence[str], None] = '1ff394370c79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create places_search table for simple search
    op.create_table(
        'places_search',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('place_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(256), nullable=True),
        sa.Column('category', sa.String(64), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('tags_csv', sa.Text(), nullable=True),
        sa.Column('lat', sa.Float(), nullable=True),
        sa.Column('lng', sa.Float(), nullable=True),
        sa.Column('picture_url', sa.String(), nullable=True),
        sa.Column('processing_status', sa.String(16), nullable=True),
        sa.Column('search_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for search
    op.create_index('idx_places_search_name', 'places_search', ['name'])
    op.create_index('idx_places_search_category', 'places_search', ['category'])
    op.create_index('idx_places_search_status', 'places_search', ['processing_status'])
    op.create_index('idx_places_search_text', 'places_search', ['search_text'])
    
    # Populate with data from places table
    op.execute("""
        INSERT INTO places_search (place_id, name, category, summary, tags_csv, lat, lng, picture_url, processing_status, search_text, created_at)
        SELECT 
            id as place_id,
            name,
            category,
            summary,
            tags_csv,
            lat,
            lng,
            picture_url,
            processing_status,
            COALESCE(name, '') || ' ' || COALESCE(tags_csv, '') || ' ' || COALESCE(summary, '') || ' ' || COALESCE(category, '') as search_text,
            CURRENT_TIMESTAMP as created_at
        FROM places
        WHERE processing_status IN ('published', 'summarized', 'new')
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('places_search')
