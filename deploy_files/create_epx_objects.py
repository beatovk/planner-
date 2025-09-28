#!/usr/bin/env python3
import sys
from sqlalchemy import create_engine, text

POSTGRES_DSN = "postgresql+psycopg://postgres:1234@localhost:5432/ep"

DDL_STATEMENTS = [
    # 1) Create schema owned by ep
    "CREATE SCHEMA IF NOT EXISTS epx AUTHORIZATION ep;",
    # 2) Ensure privileges in schema for ep
    "GRANT USAGE, CREATE ON SCHEMA epx TO ep;",
    # 3) Materialized view with search_vector and inline signals from places
    "CREATE MATERIALIZED VIEW IF NOT EXISTS epx.places_search_mv AS\n"
    "SELECT\n"
    "  p.id, p.name, p.category, p.summary, p.tags_csv, p.lat, p.lng,\n"
    "  p.picture_url, p.gmaps_place_id, p.gmaps_url, p.rating, p.processing_status,\n"
    "  to_tsvector('simple', coalesce(p.name,'') || ' ' || coalesce(p.category,'') || ' ' || coalesce(p.tags_csv,'') || ' ' || coalesce(p.summary,'')) AS search_vector,\n"
    "  COALESCE(p.signals, '{}'::jsonb) AS signals\n"
    "FROM public.places p;",
    # 4) Indexes for MV
    "CREATE UNIQUE INDEX IF NOT EXISTS places_search_mv_pk ON epx.places_search_mv (id);",
    "CREATE INDEX IF NOT EXISTS places_search_mv_gin ON epx.places_search_mv USING gin (search_vector);",
    "CREATE INDEX IF NOT EXISTS places_search_mv_signals_gin ON epx.places_search_mv USING gin (signals);",
]

def main() -> int:
    engine = create_engine(POSTGRES_DSN)
    try:
        with engine.begin() as conn:
            for stmt in DDL_STATEMENTS:
                conn.execute(text(stmt))
        # Refresh MV after creation
        with engine.begin() as conn:
            conn.execute(text("REFRESH MATERIALIZED VIEW epx.places_search_mv;"))
        print("OK: epx schema objects created and MV refreshed")
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
