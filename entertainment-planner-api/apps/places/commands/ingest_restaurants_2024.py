#!/usr/bin/env python3
"""Command to ingest 50 new Bangkok restaurants from BK Magazine 2024 article"""

import sys
import os
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../..'))

from apps.core.db import SessionLocal
from apps.places.models import Place
from apps.places.ingestion.bk_magazine_adapter import BKMagazineAdapter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def ingest_restaurants_2024():
    """Ingest 50 new Bangkok restaurants from BK Magazine 2024 article"""
    logger.info("Starting ingestion of 50 new Bangkok restaurants 2024")
    
    # Initialize adapter
    adapter = BKMagazineAdapter()
    
    # Parse the article
    url = 'https://bk.asia-city.com/restaurants/news/50-new-bangkok-restaurants-opened-2024-you-to-check-out'
    places_data = adapter.parse_article_page(url)
    
    logger.info(f"Found {len(places_data)} places in article")
    
    # Initialize database
    db = SessionLocal()
    
    try:
        success_count = 0
        error_count = 0
        
        for i, place_data in enumerate(places_data, 1):
            try:
                # Create unique source URL
                unique_source_url = f"{url}#{i}"
                
                # Check if place already exists
                existing_place = db.query(Place).filter(
                    Place.source_url == unique_source_url
                ).first()
                
                if existing_place:
                    logger.info(f"Place {i} already exists, skipping: {place_data['title']}")
                    continue
                
                # Create place object
                place = Place(
                    source='bk_magazine',
                    source_url=unique_source_url,
                    raw_payload=f"<article>{place_data['title']}</article>",
                    scraped_at=datetime.utcnow(),
                    name=place_data['title'],
                    category='Restaurant',  # All are restaurants
                    description_full=place_data['teaser'],
                    address=place_data['address_fallback'],
                    processing_status='new'
                )
                
                db.add(place)
                db.commit()
                
                success_count += 1
                logger.info(f"✅ Added place {i}: {place_data['title']}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"❌ Error adding place {i} ({place_data['title']}): {e}")
                db.rollback()
        
        logger.info(f"Ingestion completed:")
        logger.info(f"  Total processed: {len(places_data)}")
        logger.info(f"  Success: {success_count}")
        logger.info(f"  Errors: {error_count}")
        
        return {
            'total': len(places_data),
            'success': success_count,
            'errors': error_count
        }
        
    finally:
        db.close()


if __name__ == "__main__":
    result = ingest_restaurants_2024()
    print(f"Result: {result}")
