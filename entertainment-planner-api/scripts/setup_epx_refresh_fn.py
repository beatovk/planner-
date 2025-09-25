#!/usr/bin/env python3
from sqlalchemy import create_engine, text

POSTGRES_DSN = "postgresql+psycopg://postgres:1234@localhost:5432/ep"

SQL_STATEMENTS = [
    # Heartbeat таблица
    """
    CREATE TABLE IF NOT EXISTS epx.mv_refresh_heartbeat(
      mv_name text PRIMARY KEY,
      refreshed_at timestamptz NOT NULL DEFAULT now()
    );
    """,
    # Функция с апдейтом heartbeat
    """
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
    $$;
    """,
    # Grant execute to app user
    "GRANT EXECUTE ON FUNCTION epx.refresh_places_search_mv() TO ep;",
    # Create geo btree index on MV for (lat,lng)
    "CREATE INDEX IF NOT EXISTS places_search_mv_lat_lng_idx ON epx.places_search_mv (lat, lng);",
]

def main() -> int:
    engine = create_engine(POSTGRES_DSN)
    try:
        with engine.begin() as conn:
            for stmt in SQL_STATEMENTS:
                conn.execute(text(stmt))
        print("OK: refresh function and geo index set up")
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
