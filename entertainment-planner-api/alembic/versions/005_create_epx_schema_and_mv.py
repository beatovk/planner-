"""Create epx schema and materialized view

Revision ID: 005_create_epx_schema_and_mv
Revises: de0311f798f2
Create Date: 2025-01-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '005_create_epx_schema_and_mv'
down_revision = 'de0311f798f2'
branch_labels = None
depends_on = None

def upgrade():
    """Create epx schema and materialized view for PostgreSQL FTS"""
    
    # 1. Create epx schema
    op.execute(text("CREATE SCHEMA IF NOT EXISTS epx"))
    
    # 2. Grant permissions to epx schema
    op.execute(text("GRANT USAGE, CREATE ON SCHEMA epx TO ep"))
    
    # 3. Create materialized view with search_vector and signals
    op.execute(text("""
        CREATE MATERIALIZED VIEW epx.places_search_mv AS
        SELECT
            p.id, p.name, p.category, p.summary, p.tags_csv, p.lat, p.lng,
            p.picture_url, p.gmaps_place_id, p.gmaps_url, p.rating, p.processing_status,
            to_tsvector('simple', 
                coalesce(p.name,'') || ' ' || 
                coalesce(p.category,'') || ' ' || 
                coalesce(p.tags_csv,'') || ' ' || 
                coalesce(p.summary,'') || ' ' ||
                coalesce(p.description_full,'')
            ) AS search_vector,
            COALESCE(p.signals, '{}'::jsonb) AS signals
        FROM public.places p
        WHERE p.processing_status IN ('published', 'summarized', 'new')
    """))
    
    # 4. Create indexes for materialized view
    op.execute(text("CREATE UNIQUE INDEX places_search_mv_pk ON epx.places_search_mv (id)"))
    op.execute(text("CREATE INDEX places_search_mv_gin ON epx.places_search_mv USING gin (search_vector)"))
    op.execute(text("CREATE INDEX places_search_mv_signals_gin ON epx.places_search_mv USING gin (signals)"))
    op.execute(text("CREATE INDEX places_search_mv_lat_lng_idx ON epx.places_search_mv (lat, lng)"))
    op.execute(text("CREATE INDEX places_search_mv_status_idx ON epx.places_search_mv (processing_status)"))
    
    # 5. Create heartbeat table for MV refresh tracking
    op.execute(text("""
        CREATE TABLE IF NOT EXISTS epx.mv_refresh_heartbeat(
            mv_name text PRIMARY KEY,
            refreshed_at timestamptz NOT NULL DEFAULT now()
        )
    """))
    
    # 6. Create refresh function
    op.execute(text("""
        CREATE OR REPLACE FUNCTION epx.refresh_places_search_mv()
        RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW CONCURRENTLY epx.places_search_mv;
            INSERT INTO epx.mv_refresh_heartbeat (mv_name, refreshed_at)
            VALUES ('places_search_mv', now())
            ON CONFLICT (mv_name) DO UPDATE SET refreshed_at = EXCLUDED.refreshed_at;
        END;
        $$
    """))
    
    # 7. Grant execute permission
    op.execute(text("GRANT EXECUTE ON FUNCTION epx.refresh_places_search_mv() TO ep"))

def downgrade():
    """Drop epx schema and materialized view"""
    
    # Drop function
    op.execute(text("DROP FUNCTION IF EXISTS epx.refresh_places_search_mv()"))
    
    # Drop materialized view
    op.execute(text("DROP MATERIALIZED VIEW IF EXISTS epx.places_search_mv"))
    
    # Drop heartbeat table
    op.execute(text("DROP TABLE IF EXISTS epx.mv_refresh_heartbeat"))
    
    # Drop schema
    op.execute(text("DROP SCHEMA IF EXISTS epx"))