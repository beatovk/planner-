#!/usr/bin/env python3
"""
Load published places from CSV into PostgreSQL database
"""
import os
import sys
import csv
import json
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

def require_env(name: str) -> str:
    """Require environment variable"""
    value = os.getenv(name)
    if not value:
        print(f"ENV {name} is required", file=sys.stderr)
        sys.exit(1)
    return value

def parse_row(row: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Parse CSV row into database record"""
    def to_float(x: str) -> Optional[float]:
        try:
            return float(x) if x not in (None, "", "null", "None") else None
        except Exception:
            return None

    def to_int(x: str) -> Optional[int]:
        try:
            return int(x) if x not in (None, "", "null", "None") else None
        except Exception:
            return None

    def parse_json(x: str) -> Optional[Dict]:
        try:
            return json.loads(x) if x and x != "null" else None
        except Exception:
            return None

    out = {
        "id": to_int(row.get("id", "")),
        "name": (row.get("name") or "").strip() or None,
        "category": (row.get("category") or "").strip() or None,
        "summary": (row.get("summary") or None),
        "tags_csv": (row.get("tags_csv") or None),
        "lat": to_float(row.get("lat", "")),
        "lng": to_float(row.get("lng", "")),
        "address": (row.get("address") or None),
        "price_level": to_int(row.get("price_level", "")),
        "rating": to_float(row.get("rating", "")),
        "picture_url": (row.get("picture_url") or None),
        "website": (row.get("website") or None),
        "phone": (row.get("phone") or None),
        "processing_status": "published",
        "published_at": datetime.now(),
        "signals": parse_json(row.get("signals", "")),
        "interest_signals": parse_json(row.get("interest_signals", ""))
    }
    
    # Validation
    if not out["name"] or out["lat"] is None or out["lng"] is None:
        return None
    return out

def upsert_place(engine: Engine, rec: Dict[str, Any]) -> None:
    """Upsert place record"""
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO places (
                    id, name, category, summary, tags_csv, lat, lng, address, 
                    price_level, rating, picture_url, website, phone, 
                    processing_status, published_at, signals, interest_signals
                )
                VALUES (
                    :id, :name, :category, :summary, :tags_csv, :lat, :lng, :address,
                    :price_level, :rating, :picture_url, :website, :phone,
                    :processing_status, :published_at, :signals, :interest_signals
                )
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    category = EXCLUDED.category,
                    summary = EXCLUDED.summary,
                    tags_csv = EXCLUDED.tags_csv,
                    lat = EXCLUDED.lat,
                    lng = EXCLUDED.lng,
                    address = EXCLUDED.address,
                    price_level = EXCLUDED.price_level,
                    rating = EXCLUDED.rating,
                    picture_url = EXCLUDED.picture_url,
                    website = EXCLUDED.website,
                    phone = EXCLUDED.phone,
                    processing_status = EXCLUDED.processing_status,
                    published_at = EXCLUDED.published_at,
                    signals = EXCLUDED.signals,
                    interest_signals = EXCLUDED.interest_signals,
                    updated_at = NOW()
            """),
            rec
        )

def main():
    """Main function"""
    # Get database URL
    db_url = require_env("DATABASE_URL")
    
    # Validate PostgreSQL
    if not (db_url.startswith("postgresql://") or db_url.startswith("postgresql+psycopg://")):
        print("ERROR: PostgreSQL required", file=sys.stderr)
        sys.exit(1)
    
    # Get CSV file path
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "published_places_with_signals.csv"
    
    if not os.path.exists(csv_file):
        print(f"ERROR: CSV file not found: {csv_file}", file=sys.stderr)
        sys.exit(1)
    
    # Create engine
    engine = create_engine(db_url)
    
    # Load and process CSV
    loaded = 0
    skipped = 0
    
    print(f"Loading places from {csv_file}...")
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rec = parse_row(row)
            if rec:
                upsert_place(engine, rec)
                loaded += 1
                if loaded % 100 == 0:
                    print(f"Loaded {loaded} places...")
            else:
                skipped += 1
    
    # Refresh materialized view
    print("Refreshing materialized view...")
    with engine.begin() as conn:
        conn.execute(text("SELECT epx.refresh_places_search_mv()"))
    
    print(f"✅ Loaded {loaded} places, skipped {skipped} invalid records")
    print("✅ Materialized view refreshed")

if __name__ == "__main__":
    main()
