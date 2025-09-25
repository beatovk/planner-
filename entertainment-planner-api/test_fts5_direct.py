#!/usr/bin/env python3
import os
from sqlalchemy import create_engine, text

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://ep:ep@localhost:5432/ep")
if not (DB_URL.startswith("postgresql://") or DB_URL.startswith("postgresql+psycopg://")):
    raise RuntimeError(f"PostgreSQL required: {DB_URL}")
engine = create_engine(DB_URL)

print("Testing FTS5 directly...")

with engine.begin() as conn:
    # 1) Проверка что materialized view существует
    try:
        result = conn.execute(text("SELECT COUNT(*) FROM epx.places_search_mv")).scalar()
        print(f"✅ PostgreSQL search view exists with {result} rows")
    except Exception as e:
        print(f"❌ PostgreSQL search view error: {e}")
        exit(1)
    
    # 2) Простой FTS запрос
    try:
        result = conn.execute(text("SELECT name FROM epx.places_search_mv WHERE search_vector @@ websearch_to_tsquery('english', 'club') LIMIT 5")).fetchall()
        print(f"✅ Simple PostgreSQL FTS search found {len(result)} results:")
        for row in result:
            print(f"  - {row[0]}")
    except Exception as e:
        print(f"❌ Simple PostgreSQL FTS search error: {e}")
    
    # 3) Сложный FTS запрос как в коде
    try:
        match_query = "club"
        
        sql = text("""
            SELECT 
                p.id, p.name, p.category, p.summary, p.tags_csv,
                p.lat, p.lng, p.address, p.price_level, p.picture_url,
                p.gmaps_place_id, p.processing_status, p.updated_at, p.published_at,
                ts_rank(mv.search_vector, websearch_to_tsquery('english', :match_query)) AS ts_rank_score
            FROM epx.places_search_mv mv
            JOIN places p ON mv.id = p.id
            WHERE mv.search_vector @@ websearch_to_tsquery('english', :match_query)
              AND p.processing_status IN ('published','summarized')
            ORDER BY ts_rank_score DESC
            LIMIT 5 OFFSET 0
        """)
        
        result = conn.execute(sql, {"match_query": match_query}).fetchall()
        print(f"✅ Complex PostgreSQL FTS search found {len(result)} results:")
        for row in result:
            print(f"  - {row[1]} ({row[2]}) - score: {row[-1]}")
    except Exception as e:
        print(f"❌ Complex PostgreSQL FTS search error: {e}")
    
    # 4) Проверка данных в places
    try:
        result = conn.execute(text("SELECT COUNT(*) FROM places WHERE processing_status IN ('published','summarized')")).scalar()
        print(f"✅ Places table has {result} published/summarized records")
    except Exception as e:
        print(f"❌ Places table error: {e}")
