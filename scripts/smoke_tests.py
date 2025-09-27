#!/usr/bin/env python3
"""Minimal smoke tests that exercise the public rails endpoint."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

QUERY = "i wanna chill movie and something romantic"
LAT = 13.744262
LNG = 100.561473
LIMIT = 6
ROMANTIC_TAGS = {"romantic", "sunset", "skyline", "candle", "candlelight", "river"}


def _build_url(base: str) -> str:
    params = {
        "q": QUERY,
        "limit": str(LIMIT),
        "user_lat": f"{LAT}",
        "user_lng": f"{LNG}",
    }
    return f"{base.rstrip('/')}/api/rails?{urllib.parse.urlencode(params)}"


def _load_payload(url: str) -> dict:
    try:
        with urllib.request.urlopen(url) as response:
            return json.load(response)
    except urllib.error.URLError as exc:  # pragma: no cover - network failure
        print(f"Request to {url} failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _romantic_score(item: dict) -> bool:
    signals = item.get("signals") or {}
    if signals.get("dateworthy") is True:
        return True
    tags_blob = " ".join(
        [item.get("tags_csv") or "", " ".join(item.get("tags", []))]
    ).lower()
    return any(tag in tags_blob for tag in ROMANTIC_TAGS)


def main() -> None:
    base = os.environ.get("BASE", "http://localhost:8000")
    url = _build_url(base)
    payload = _load_payload(url)

    rails = {
        (rail.get("label") or rail.get("type") or "").strip().lower(): rail
        for rail in payload.get("rails", [])
    }

    required = ["chill", "cinema", "romantic"]
    missing = [name for name in required if name not in rails]
    if missing:
        raise AssertionError(f"Missing rails: {missing}")

    for name in required:
        items = rails[name].get("items", [])
        if not items:
            raise AssertionError(f"Rail '{name}' has no items")

    romantic_items = rails["romantic"].get("items", [])
    if romantic_items:
        romantic_hits = sum(1 for item in romantic_items if _romantic_score(item))
        if romantic_hits * 2 < len(romantic_items):
            raise AssertionError(
                "Romantic rail failed semantic check: insufficient romantic items"
            )

    print("✅ Acceptance Case A passed")


if __name__ == "__main__":
    main()
