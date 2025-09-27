#!/usr/bin/env python3
"""
Load data via API calls to staging
"""
import requests
import json
import csv
import time
from typing import Dict, Any, Optional

def parse_row(row: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Parse CSV row into API payload"""
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
        "signals": parse_json(row.get("signals", "")),
        "interest_signals": parse_json(row.get("interest_signals", ""))
    }
    
    # Validation
    if not out["name"] or out["lat"] is None or out["lng"] is None:
        return None
    return out

def load_place_via_api(place_data: Dict[str, Any], base_url: str) -> bool:
    """Load place via API"""
    try:
        # Create place
        response = requests.post(
            f"{base_url}/api/places",
            json=place_data,
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            return True
        elif response.status_code == 409:  # Conflict - place already exists
            # Try to update
            update_response = requests.put(
                f"{base_url}/api/places/{place_data['id']}",
                json=place_data,
                timeout=30
            )
            return update_response.status_code in [200, 201]
        else:
            print(f"Failed to load place {place_data['id']}: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"Error loading place {place_data['id']}: {e}")
        return False

def main():
    """Main function"""
    import sys
    
    # Get CSV file path
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "published_places_with_signals.csv"
    
    # Get base URL
    base_url = sys.argv[2] if len(sys.argv) > 2 else "https://entertainment-planner-staging.fly.dev"
    
    if not csv_file:
        print("ERROR: CSV file path required", file=sys.stderr)
        sys.exit(1)
    
    # Load and process CSV
    loaded = 0
    skipped = 0
    failed = 0
    
    print(f"Loading places from {csv_file} to {base_url}...")
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rec = parse_row(row)
            if rec:
                if load_place_via_api(rec, base_url):
                    loaded += 1
                    if loaded % 10 == 0:
                        print(f"Loaded {loaded} places...")
                        time.sleep(0.1)  # Rate limiting
                else:
                    failed += 1
            else:
                skipped += 1
    
    print(f"✅ Loaded {loaded} places, skipped {skipped} invalid records, failed {failed}")

if __name__ == "__main__":
    main()
