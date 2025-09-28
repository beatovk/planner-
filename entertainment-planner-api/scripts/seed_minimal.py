#!/usr/bin/env python3
"""
Minimal seed script for PostgreSQL places table
"""
from __future__ import annotations
import os, json, datetime as dt
from typing import Any, Dict
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise SystemExit("DATABASE_URL is empty")

engine = create_engine(DB_URL, future=True, pool_pre_ping=True)

def get_places_columns() -> Dict[str,str]:
    sql = text("""
      SELECT column_name, data_type
      FROM information_schema.columns
      WHERE table_schema='public' AND table_name='places'
      ORDER BY ordinal_position
    """)
    with engine.begin() as c:
        rows = c.execute(sql).all()
    return {r[0]: r[1] for r in rows}

def coerce_payload(cols: Dict[str,str], payload: Dict[str, Any]) -> Dict[str, Any]:
    """Оставляем только существующие колонки и приводим signals к JSONB."""
    out: Dict[str, Any] = {}
    for k,v in payload.items():
        if k not in cols:
            continue
        if k == "signals":
            # строка JSON — psycopg3 сам сконвертит в jsonb
            out[k] = json.dumps(v) if isinstance(v, (dict, list)) else v
        else:
            out[k] = v
    # timestamps, если есть
    now = dt.datetime.utcnow()
    for k in ("created_at","updated_at","published_at"):
        if k in cols and k not in out:
            out[k] = now
    # processing_status по умолчанию
    if "processing_status" in cols and "processing_status" not in out:
        out["processing_status"] = "published"
    return out

def insert_place(payload: Dict[str,Any]) -> int:
    cols = get_places_columns()
    data = coerce_payload(cols, payload)
    if not data:
        raise RuntimeError("No columns match schema; check table 'places'")
    # строим INSERT с :name плейсхолдерами
    columns = ", ".join(data.keys())
    placeholders = ", ".join(f":{k}" for k in data.keys())
    sql = text(f"INSERT INTO public.places ({columns}) VALUES ({placeholders}) RETURNING id")
    with engine.begin() as c:
        new_id = c.execute(sql, data).scalar_one()
    return int(new_id)

def refresh_mv():
    # безопасный рефреш: если MV нет — не падаем
    with engine.begin() as c:
        c.execute(text("DO $$ BEGIN IF to_regclass('epx.places_search_mv') IS NOT NULL THEN REFRESH MATERIALIZED VIEW epx.places_search_mv; END IF; END $$;"))

def main():
    print("🔍 Checking places table schema...")
    cols = get_places_columns()
    print(f"📋 Found {len(cols)} columns in places table:")
    for col, dtype in cols.items():
        print(f"  - {col}: {dtype}")
    
    examples = [
        {
            "name": "Chill Cafe",
            "category": "cafe",
            "summary": "A peaceful cafe for relaxation",
            "tags_csv": "coffee,relax,chill,ambient",
            "lat": 13.7563, "lng": 100.5018,
            "picture_url": "https://example.com/chill.jpg",
            "gmaps_place_id": "test_chill_1",
            "gmaps_url": "https://maps.google.com/test_chill_1",
            "rating": 4.5,
            "signals": {"lounge": True, "ambient": True, "tea": True}
        },
        {
            "name": "Skyline Rooftop",
            "category": "bar",
            "summary": "Rooftop bar with sunset view",
            "tags_csv": "rooftop,view,romantic,sunset",
            "lat": 13.743, "lng": 100.562,
            "picture_url": "https://example.com/roof.jpg",
            "gmaps_place_id": "test_rom_1",
            "gmaps_url": "https://maps.google.com/test_rom_1",
            "rating": 4.6,
            "signals": {"romantic": True, "dateworthy": True}
        },
        {
            "name": "Central Cinema",
            "category": "cinema",
            "summary": "Movie theater downtown",
            "tags_csv": "cinema,movie",
            "lat": 13.75, "lng": 100.5,
            "gmaps_place_id": "test_cinema_1",
            "gmaps_url": "https://maps.google.com/test_cinema_1",
            "rating": 4.2,
            "signals": {"cinema": True}
        },
    ]
    
    print(f"\n🌱 Inserting {len(examples)} test places...")
    ids = []
    for i, example in enumerate(examples, 1):
        try:
            new_id = insert_place(example)
            ids.append(new_id)
            print(f"  ✅ {i}. {example['name']} -> ID {new_id}")
        except Exception as e:
            print(f"  ❌ {i}. {example['name']} -> Error: {e}")
    
    print(f"\n🔄 Refreshing materialized view...")
    try:
        refresh_mv()
        print("  ✅ MV refreshed successfully")
    except Exception as e:
        print(f"  ❌ MV refresh failed: {e}")
    
    print(f"\n📊 Summary: Inserted {len(ids)} places with IDs: {ids}")

if __name__ == "__main__":
    main()
