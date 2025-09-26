"""Extend places_search table for slotter functionality

Revision ID: 005_extend_places_search_for_slotter
Revises: 4b01b85814cc
Create Date: 2025-01-21 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_extend_places_search_for_slotter'
down_revision = '4b01b85814cc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Extend places_search table for slotter functionality."""
    
    # Add new columns to places_search table
    op.add_column('places_search', sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True))
    op.add_column('places_search', sa.Column('signals', postgresql.JSONB(astext_type=sa.Text()), nullable=True, default={}))
    op.add_column('places_search', sa.Column('processing_status', sa.String(16), nullable=True, default='published'))
    
    # Create epx schema
    op.execute('CREATE SCHEMA IF NOT EXISTS epx')
    
    # Create materialized view for FTS
    op.execute("""
        CREATE MATERIALIZED VIEW epx.places_search_mv AS
        SELECT 
            id, name, category, summary, tags_csv, lat, lng,
            picture_url, processing_status, signals,
            to_tsvector('simple', 
                COALESCE(name, '') || ' ' || 
                COALESCE(category, '') || ' ' || 
                COALESCE(summary, '') || ' ' || 
                COALESCE(tags_csv, '')
            ) as search_vector
        FROM places_search
        WHERE processing_status IN ('published', 'summarized', 'new')
    """)
    
    # Create indexes for FTS
    op.execute('CREATE INDEX idx_places_search_mv_vector ON epx.places_search_mv USING GIN(search_vector)')
    op.execute('CREATE INDEX idx_places_search_mv_status ON epx.places_search_mv(processing_status)')
    op.execute('CREATE INDEX idx_places_search_mv_signals ON epx.places_search_mv USING GIN(signals)')
    
    # Create function to refresh materialized view
    op.execute("""
        CREATE OR REPLACE FUNCTION epx.refresh_places_search_mv()
        RETURNS void AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW epx.places_search_mv;
        END;
        $$ LANGUAGE plpgsql
    """)


def downgrade() -> None:
    """Remove slotter functionality."""
    
    # Drop materialized view and schema
    op.execute('DROP MATERIALIZED VIEW IF EXISTS epx.places_search_mv')
    op.execute('DROP FUNCTION IF EXISTS epx.refresh_places_search_mv()')
    op.execute('DROP SCHEMA IF EXISTS epx CASCADE')
    
    # Remove columns from places_search
    op.drop_column('places_search', 'processing_status')
    op.drop_column('places_search', 'signals')
    op.drop_column('places_search', 'search_vector')
