#!/usr/bin/env python3
"""
Add test data to PostgreSQL
"""
import os
import json
from sqlalchemy import create_engine, text

def add_test_data():
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        print("❌ DATABASE_URL not set")
        return 1
    
    engine = create_engine(DATABASE_URL)
    
    test_places = [
        {
            "name": "Chill Cafe",
            "category": "Cafe",
            "summary": "A peaceful cafe for relaxation",
            "description": "Perfect place to unwind with a cup of coffee",
            "tags_csv": "coffee,relax,chill,ambient",
            "lat": 13.7563,
            "lng": 100.5018,
            "picture_url": "https://example.com/chill.jpg",
            "gmaps_place_id": "test_chill_1",
            "gmaps_url": "https://maps.google.com/test_chill_1",
            "rating": 4.5,
            "processing_status": "published",
            "signals": {"spa": True, "ambient": True, "chill": True}
        },
        {
            "name": "Romantic Rooftop",
            "category": "Restaurant",
            "summary": "Perfect for romantic dinners",
            "description": "Beautiful rooftop restaurant with sunset views",
            "tags_csv": "romantic,rooftop,sunset,date",
            "lat": 13.7233,
            "lng": 100.5801,
            "picture_url": "https://example.com/rooftop.jpg",
            "gmaps_place_id": "test_romantic_1",
            "gmaps_url": "https://maps.google.com/test_romantic_1",
            "rating": 4.8,
            "processing_status": "published",
            "signals": {"dateworthy": True, "romantic": True}
        },
        {
            "name": "Cinema Complex",
            "category": "Cinema",
            "summary": "Modern movie theater",
            "description": "Latest movies in comfortable seats",
            "tags_csv": "cinema,movie,entertainment",
            "lat": 13.7563,
            "lng": 100.5018,
            "picture_url": "https://example.com/cinema.jpg",
            "gmaps_place_id": "test_cinema_1",
            "gmaps_url": "https://maps.google.com/test_cinema_1",
            "rating": 4.2,
            "processing_status": "published",
            "signals": {"cinema": True}
        }
    ]
    
    try:
        with engine.begin() as conn:
            # Insert test data
            for place in test_places:
                # Convert signals dict to JSON string
                place_data = place.copy()
                place_data['signals'] = json.dumps(place['signals'])
                
                conn.execute(text("""
                    INSERT INTO places (name, category, summary, description, tags_csv, 
                                      lat, lng, picture_url, gmaps_place_id, gmaps_url, 
                                      rating, processing_status, signals)
                    VALUES (%(name)s, %(category)s, %(summary)s, %(description)s, %(tags_csv)s,
                           %(lat)s, %(lng)s, %(picture_url)s, %(gmaps_place_id)s, %(gmaps_url)s,
                           %(rating)s, %(processing_status)s, %(signals)s::jsonb)
                """), place_data)
            
            print(f"✅ Inserted {len(test_places)} test places")
            
            # Refresh MV
            conn.execute(text("REFRESH MATERIALIZED VIEW epx.places_search_mv"))
            print("✅ MV refreshed")
            
            # Check counts
            places_count = conn.execute(text("SELECT COUNT(*) FROM places")).scalar()
            mv_count = conn.execute(text("SELECT COUNT(*) FROM epx.places_search_mv")).scalar()
            print(f"📊 Places: {places_count}, MV: {mv_count}")
            
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    exit(add_test_data())
