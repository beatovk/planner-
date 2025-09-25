#!/usr/bin/env python3
"""
Команда для обогащения мест из BK Magazine через Google API
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from apps.core.db import SessionLocal
from apps.places.models import Place
from apps.places.commands.enrich_google import enrich_one_place, map_google_type_to_category
from apps.places.services.google_places import GooglePlaces, GooglePlacesError
import logging
import json

logger = logging.getLogger(__name__)

def normalize_bk_place_name(name: str) -> str:
    """Улучшенная нормализация названий мест из BK Magazine"""
    if not name or not name.strip():
        return ""
    
    # Очищаем название от лишней информации
    clean_name = name.strip()
    
    # Убираем префиксы и суффиксы
    prefixes_to_remove = [
        "Photo:", "NEW", "NEW:", "Finalist:", "Finalist", 
        "Leave a Comment", "Back to top", "Websites"
    ]
    
    for prefix in prefixes_to_remove:
        if clean_name.startswith(prefix):
            clean_name = clean_name[len(prefix):].strip()
            break
    
    # Убираем суффиксы в скобках
    if "(" in clean_name and ")" in clean_name:
        clean_name = clean_name.split("(")[0].strip()
    
    # Убираем лишние символы
    clean_name = clean_name.replace("/", " ").replace("–", "-").replace("—", "-")
    
    # Если название слишком длинное, берем только первые слова
    words = clean_name.split()
    if len(words) > 6:
        clean_name = " ".join(words[:6])
    
    # Добавляем Bangkok для лучшего поиска
    return f"{clean_name} Bangkok"

def enrich_bk_places(batch_size: int = 20, dry_run: bool = False):
    """Обогащение мест из BK Magazine через Google API"""
    logger.info(f"Starting BK Magazine enrichment (batch_size={batch_size}, dry_run={dry_run})")
    
    # Initialize Google Places client
    try:
        google_client = GooglePlaces()
    except Exception as e:
        logger.warning(f"Failed to initialize Google Places client: {e}")
        logger.info("Using mock mode for testing...")
        google_client = GooglePlaces(mock_mode=True)
    
    # Get BK Magazine places that need enrichment
    db = SessionLocal()
    try:
        # Query BK Magazine places that don't have Google Maps data yet
        places_query = db.query(Place).filter(
            Place.source == 'bk_magazine'
        ).filter(
            Place.gmaps_place_id.is_(None)
        ).limit(batch_size)
        
        places = places_query.all()
        total_places = len(places)
        
        if total_places == 0:
            logger.info("No BK Magazine places found for enrichment")
            return
        
        logger.info(f"Found {total_places} BK Magazine places to enrich")
        
        # Process each place
        success_count = 0
        error_count = 0
        
        for i, place in enumerate(places, 1):
            logger.info(f"Processing place {i}/{total_places}: {place.name}")
            
            try:
                # Улучшенная нормализация названия
                search_text = normalize_bk_place_name(place.name)
                logger.info(f"Searching for: {search_text}")
                
                # Find place
                try:
                    find_result = google_client.find_place(
                        search_text, 
                        lat=place.lat, 
                        lng=place.lng
                    )
                except GooglePlacesError as e:
                    logger.warning(f"API error, switching to mock mode: {e}")
                    google_client = GooglePlaces(mock_mode=True)
                    find_result = google_client.find_place(
                        search_text, 
                        lat=place.lat, 
                        lng=place.lng
                    )
                
                if not find_result:
                    logger.warning(f"❌ Place {place.id} failed: No candidates found")
                    error_count += 1
                    continue
                
                place_id = find_result.get("id")
                if not place_id:
                    logger.warning(f"❌ Place {place.id} failed: No place_id in find result")
                    error_count += 1
                    continue
                
                # Get place details
                details = google_client.place_details(place_id)
                if not details:
                    logger.warning(f"❌ Place {place.id} failed: No details found")
                    error_count += 1
                    continue
                
                # Update place with Google Maps data
                if not dry_run:
                    place.gmaps_place_id = place_id
                    place.gmaps_url = f"https://maps.google.com/?cid={place_id}"
                    
                    # Always update coordinates from Google Maps (more accurate)
                    if details.get("location"):
                        location = details["location"]
                        place.lat = location["latitude"]
                        place.lng = location["longitude"]
                    
                    # Always update address from Google Maps (more reliable)
                    if details.get("formattedAddress"):
                        place.address = details["formattedAddress"]
                    
                    # Update price level
                    if details.get("priceLevel") is not None:
                        price_level = details["priceLevel"]
                        # Convert string price levels to integers
                        if isinstance(price_level, str):
                            price_map = {
                                "PRICE_LEVEL_FREE": 0,
                                "PRICE_LEVEL_INEXPENSIVE": 1,
                                "PRICE_LEVEL_MODERATE": 2,
                                "PRICE_LEVEL_EXPENSIVE": 3,
                                "PRICE_LEVEL_VERY_EXPENSIVE": 4
                            }
                            price_level = price_map.get(price_level, price_level)
                        place.price_level = price_level
                    
                    # Update business status
                    if details.get("businessStatus"):
                        place.business_status = details["businessStatus"]
                    
                    # Update UTC offset
                    if details.get("utcOffsetMinutes") is not None:
                        place.utc_offset_minutes = details["utcOffsetMinutes"]
                    
                    # Always update hours from Google Maps (more reliable than TimeOut)
                    if details.get("regularOpeningHours"):
                        hours = details["regularOpeningHours"]
                        if hours:
                            place.hours_json = json.dumps(hours)
                    
                    # Update category from Google Places types (most reliable source)
                    if details.get("types"):
                        google_types = details["types"]
                        new_category = map_google_type_to_category(google_types)
                        if new_category != place.category:
                            logger.info(f"Updating category: {place.category} -> {new_category} (Google types: {google_types})")
                            place.category = new_category
                
                logger.info(f"✅ Place {place.id} enriched successfully")
                success_count += 1
                
            except Exception as e:
                logger.error(f"❌ Place {place.id} failed: {e}")
                error_count += 1
        
        # Commit changes
        if not dry_run:
            db.commit()
            logger.info("Changes committed to database")
        
        logger.info(f"BK Magazine enrichment completed:")
        logger.info(f"  Total processed: {total_places}")
        logger.info(f"  Success: {success_count}")
        logger.info(f"  Errors: {error_count}")
        
    except Exception as e:
        logger.error(f"Critical error in enrich_bk_places: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    enrich_bk_places()
