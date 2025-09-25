#!/usr/bin/env python3
"""
Sync published places from CSV into a Postgres database safely (upsert) and refresh MV.

Usage:
  DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db \
  python scripts/sync_published_from_csv.py --csv export_published_places.csv --refresh-mv

Notes:
  - CSV columns expected: id,name,category,summary,tags_csv,lat,lng,address,price_level,picture_url,gmaps_place_id,gmaps_url,source,source_url,published_at
  - Upsert key preference: id if present else source_url
  - Only rows with non-empty name/category/lat/lng are upserted
"""
from __future__ import annotations

import os
import sys
import csv
from typing import Dict, Any, Optional
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"ENV {name} is required", file=sys.stderr)
        sys.exit(1)
    return value


def parse_row(row: Dict[str, str]) -> Optional[Dict[str, Any]]:
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
        "picture_url": (row.get("picture_url") or None),
        "gmaps_place_id": (row.get("gmaps_place_id") or None),
        "gmaps_url": (row.get("gmaps_url") or None),
        "source": (row.get("source") or None),
        "source_url": (row.get("source_url") or None),
        "published_at": (row.get("published_at") or None),
    }
    # Minimal validation for published entries
    if not out["name"] or out["lat"] is None or out["lng"] is None:
        return None
    return out


def upsert(engine: Engine, rec: Dict[str, Any]) -> None:
    # Prefer id key if present; else source_url
    with engine.begin() as conn:
        if rec["id"]:
            # Try upsert by id
            conn.execute(
                text(
                    """
                    insert into places (id, name, category, summary, tags_csv, lat, lng, address, price_level, picture_url,
                                        gmaps_place_id, gmaps_url, source, source_url, processing_status, published_at)
                    values (:id, :name, :category, :summary, :tags_csv, :lat, :lng, :address, :price_level, :picture_url,
                            :gmaps_place_id, :gmaps_url, :source, :source_url, 'published', COALESCE(:published_at, NOW()))
                    on conflict (id) do update set
                        name = EXCLUDED.name,
                        category = EXCLUDED.category,
                        summary = EXCLUDED.summary,
                        tags_csv = EXCLUDED.tags_csv,
                        lat = EXCLUDED.lat,
                        lng = EXCLUDED.lng,
                        address = EXCLUDED.address,
                        price_level = EXCLUDED.price_level,
                        picture_url = EXCLUDED.picture_url,
                        gmaps_place_id = EXCLUDED.gmaps_place_id,
                        gmaps_url = EXCLUDED.gmaps_url,
                        source = EXCLUDED.source,
                        source_url = EXCLUDED.source_url,
                        processing_status = 'published',
                        published_at = COALESCE(EXCLUDED.published_at, NOW())
                    """
                ),
                rec,
            )
        elif rec["source_url"]:
            # Upsert by source_url
            conn.execute(
                text(
                    """
                    insert into places (name, category, summary, tags_csv, lat, lng, address, price_level, picture_url,
                                        gmaps_place_id, gmaps_url, source, source_url, processing_status, published_at)
                    values (:name, :category, :summary, :tags_csv, :lat, :lng, :address, :price_level, :picture_url,
                            :gmaps_place_id, :gmaps_url, :source, :source_url, 'published', COALESCE(:published_at, NOW()))
                    on conflict (source_url) do update set
                        name = EXCLUDED.name,
                        category = EXCLUDED.category,
                        summary = EXCLUDED.summary,
                        tags_csv = EXCLUDED.tags_csv,
                        lat = EXCLUDED.lat,
                        lng = EXCLUDED.lng,
                        address = EXCLUDED.address,
                        price_level = EXCLUDED.price_level,
                        picture_url = EXCLUDED.picture_url,
                        gmaps_place_id = EXCLUDED.gmaps_place_id,
                        gmaps_url = EXCLUDED.gmaps_url,
                        source = EXCLUDED.source,
                        processing_status = 'published',
                        published_at = COALESCE(EXCLUDED.published_at, NOW())
                    """
                ),
                rec,
            )


def refresh_mv(engine: Engine) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(text("SELECT epx.refresh_places_search_mv();"))
    except Exception as e:
        print(f"[WARN] MV refresh failed: {e}")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--refresh-mv", action="store_true")
    args = parser.parse_args()

    db_url = require_env("DATABASE_URL")
    engine = create_engine(db_url, pool_pre_ping=True)

    total_in = 0
    total_ok = 0
    with open(args.csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_in += 1
            rec = parse_row(row)
            if not rec:
                continue
            try:
                upsert(engine, rec)
                total_ok += 1
            except Exception as e:
                print(f"[ERR] upsert failed for id={rec.get('id')} src={rec.get('source_url')}: {e}")

    print(f"DONE: {total_ok}/{total_in} upserted")

    if args.refresh_mv:
        refresh_mv(engine)
        print("MV refresh requested")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


