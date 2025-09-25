#!/usr/bin/env python3
import os
from sqlalchemy import create_engine, text

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://ep:ep@localhost:5432/ep")
if not (DB_URL.startswith("postgresql://") or DB_URL.startswith("postgresql+psycopg://")):
    raise RuntimeError(f"PostgreSQL required: {DB_URL}")
engine = create_engine(DB_URL)

with engine.begin() as conn:
    # Проверка наличия materialized view
    rows = conn.execute(text("SELECT 1 FROM information_schema.tables WHERE table_schema='epx' AND table_name='places_search_mv';")).fetchall()
    if not rows:
        raise SystemExit("epx.places_search_mv not found. Run alembic upgrade first.")
    
    # Обновление materialized view (PostgreSQL эквивалент FTS rebuild)
    print("Refreshing PostgreSQL materialized view...")
    conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY epx.places_search_mv;"))
    print("PostgreSQL FTS refresh complete.")
