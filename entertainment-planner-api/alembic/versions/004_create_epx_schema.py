"""Create epx schema and materialized view

Revision ID: 004_create_epx_schema
Revises: 6c51662cda39
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_create_epx_schema'
down_revision = '6c51662cda39'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create epx schema and materialized view for PostgreSQL."""
    # Get database dialect
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == 'postgresql':
        # Create epx schema
        op.execute("CREATE SCHEMA IF NOT EXISTS epx;")
        
        # Create materialized view for search
        op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS epx.places_search_mv AS
        SELECT 
            p.id,
            p.name,
            p.category,
            p.tags_csv,
            p.summary,
            p.description_full,
            p.address,
            p.lat,
            p.lng,
            p.price_level,
            p.hours_json,
            p.processing_status,
            p.published_at,
            p.updated_at,
            to_tsvector('simple', 
                COALESCE(p.name, '') || ' ' ||
                COALESCE(p.tags_csv, '') || ' ' ||
                COALESCE(p.summary, '') || ' ' ||
                COALESCE(p.category, '') || ' ' ||
                COALESCE(p.description_full, '') || ' ' ||
                COALESCE(p.address, '')
            ) as search_vector,
            '{}'::jsonb as signals,
            '[]'::jsonb as badges
        FROM places p
        WHERE p.processing_status = 'summarized';
        """)
        
        # Create indexes
        op.execute("""
        CREATE INDEX IF NOT EXISTS idx_places_search_mv_vector 
        ON epx.places_search_mv USING gin(search_vector);
        """)
        
        op.execute("""
        CREATE INDEX IF NOT EXISTS idx_places_search_mv_status 
        ON epx.places_search_mv (processing_status);
        """)
        
        op.execute("""
        CREATE INDEX IF NOT EXISTS idx_places_search_mv_location 
        ON epx.places_search_mv (lat, lng);
        """)
        
        # Create refresh function
        op.execute("""
        CREATE OR REPLACE FUNCTION epx.refresh_places_search_mv()
        RETURNS void
        LANGUAGE plpgsql
        AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW CONCURRENTLY epx.places_search_mv;
        END;
        $$;
        """)
        
        # Initial refresh
        op.execute("SELECT epx.refresh_places_search_mv();")
        
    elif dialect_name == 'sqlite':
        # SQLite: No-op, FTS5 handles search
        pass


def downgrade() -> None:
    """Drop epx schema and materialized view."""
    # Get database dialect
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == 'postgresql':
        # Drop function
        op.execute("DROP FUNCTION IF EXISTS epx.refresh_places_search_mv();")
        
        # Drop materialized view
        op.execute("DROP MATERIALIZED VIEW IF EXISTS epx.places_search_mv;")
        
        # Drop schema
        op.execute("DROP SCHEMA IF EXISTS epx CASCADE;")
        
    elif dialect_name == 'sqlite':
        # SQLite: No-op
        pass
