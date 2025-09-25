#!/usr/bin/env python3
import os
from sqlalchemy import create_engine, text

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://ep:ep@localhost:5432/ep")
if not (DB_URL.startswith("postgresql://") or DB_URL.startswith("postgresql+psycopg://")):
    raise RuntimeError(f"PostgreSQL required: {DB_URL}")
engine = create_engine(DB_URL)

with engine.begin() as conn:
    # 1) FTS5 поддержка
    try:
        conn.execute(text("SELECT 1 FROM fts_places LIMIT 1;"))
        print("OK: fts_places exists and is queryable.")
    except Exception as e:
        print("ERR: fts_places not queryable:", e)

    # 2) Согласованность rowid=id
    r = conn.execute(text("""
        SELECT COUNT(*) AS orphans
        FROM fts_places fp
        LEFT JOIN places p ON fp.rowid = p.id
        WHERE p.id IS NULL
    """)).scalar()
    print(f"OK: orphan rows = {r}")

    # 3) Счётчик документов
    fp = conn.execute(text("SELECT COUNT(*) FROM fts_places")).scalar()
    pp = conn.execute(text("SELECT COUNT(*) FROM places WHERE processing_status IN ('published','summarized')")).scalar()
    print(f"FTS docs: {fp}, places (pub/sum): {pp}")
