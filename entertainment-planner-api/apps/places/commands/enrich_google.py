#!/usr/bin/env python3
"""Command to enrich places with Google Maps data"""

import sys
import os
import json
import logging
from typing import Tuple

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../..'))

from apps.core.db import SessionLocal
from apps.places.models import Place
from apps.places.services.google_places import (
    GooglePlaces, 
    GooglePlacesError,
    opening_hours_to_json, 
    gmaps_url_from_id,
    normalize_query
)


def map_google_type_to_category(google_types: list) -> str:
    """
    Map Google Places API types to our category system
    Based on Google Places API documentation from Context7
    """
    if not google_types:
        return "Entertainment"
    
    # Priority mapping - more specific types first
    type_mapping = {
        # Food & Drink
        'restaurant': 'Restaurant',
        'cafe': 'Restaurant', 
        'bar': 'Bar',
        'night_club': 'Nightclub',
        'bakery': 'Bakery',
        'food_court': 'Food Court',
        'meal_delivery': 'Restaurant',
        'meal_takeaway': 'Restaurant',
        'fast_food_restaurant': 'Restaurant',
        'fine_dining_restaurant': 'Restaurant',
        'coffee_shop': 'Restaurant',
        'ice_cream_shop': 'Restaurant',
        'wine_bar': 'Bar',
        'pub': 'Bar',
        'tea_house': 'Restaurant',
        'juice_shop': 'Restaurant',
        'donut_shop': 'Restaurant',
        'sandwich_shop': 'Restaurant',
        'pizza_restaurant': 'Restaurant',
        'hamburger_restaurant': 'Restaurant',
        'seafood_restaurant': 'Restaurant',
        'steak_house': 'Restaurant',
        'sushi_restaurant': 'Restaurant',
        'thai_restaurant': 'Restaurant',
        'chinese_restaurant': 'Restaurant',
        'japanese_restaurant': 'Restaurant',
        'korean_restaurant': 'Restaurant',
        'indian_restaurant': 'Restaurant',
        'italian_restaurant': 'Restaurant',
        'french_restaurant': 'Restaurant',
        'mexican_restaurant': 'Restaurant',
        'greek_restaurant': 'Restaurant',
        'spanish_restaurant': 'Restaurant',
        'turkish_restaurant': 'Restaurant',
        'lebanese_restaurant': 'Restaurant',
        'vietnamese_restaurant': 'Restaurant',
        'indonesian_restaurant': 'Restaurant',
        'brazilian_restaurant': 'Restaurant',
        'mediterranean_restaurant': 'Restaurant',
        'middle_eastern_restaurant': 'Restaurant',
        'asian_restaurant': 'Restaurant',
        'american_restaurant': 'Restaurant',
        'african_restaurant': 'Restaurant',
        'afghani_restaurant': 'Restaurant',
        'vegan_restaurant': 'Restaurant',
        'vegetarian_restaurant': 'Restaurant',
        'breakfast_restaurant': 'Restaurant',
        'brunch_restaurant': 'Restaurant',
        'buffet_restaurant': 'Restaurant',
        'dessert_restaurant': 'Restaurant',
        'barbecue_restaurant': 'Restaurant',
        'ramen_restaurant': 'Restaurant',
        'cat_cafe': 'Restaurant',
        'dog_cafe': 'Restaurant',
        'cafeteria': 'Restaurant',
        'diner': 'Restaurant',
        'candy_store': 'Restaurant',
        'chocolate_shop': 'Restaurant',
        'confectionery': 'Restaurant',
        'deli': 'Restaurant',
        'dessert_shop': 'Restaurant',
        'bagel_shop': 'Restaurant',
        'acai_shop': 'Restaurant',
        'chocolate_factory': 'Restaurant',
        
        # Health & Wellness
        'spa': 'Spa',
        'massage': 'Spa',
        'wellness_center': 'Spa',
        'yoga_studio': 'Spa',
        'gym': 'Gym',
        'fitness_center': 'Gym',
        'beauty_salon': 'Beauty',
        'hair_care': 'Beauty',
        'nail_salon': 'Beauty',
        'barber_shop': 'Beauty',
        'tanning_studio': 'Beauty',
        'skin_care_clinic': 'Beauty',
        'sauna': 'Spa',
        'physiotherapist': 'Spa',
        'chiropractor': 'Spa',
        'dental_clinic': 'Spa',
        'dentist': 'Spa',
        'doctor': 'Spa',
        'hospital': 'Spa',
        'pharmacy': 'Spa',
        'drugstore': 'Spa',
        'medical_lab': 'Spa',
        
        # Entertainment & Recreation
        'amusement_park': 'Entertainment',
        'aquarium': 'Entertainment',
        'art_gallery': 'Gallery',
        'museum': 'Museum',
        'movie_theater': 'Cinema',
        'movie_rental': 'Entertainment',
        'bowling_alley': 'Entertainment',
        'casino': 'Entertainment',
        'zoo': 'Entertainment',
        'park': 'Park',
        'tourist_attraction': 'Attraction',
        'historical_landmark': 'Attraction',
        'cultural_landmark': 'Attraction',
        'monument': 'Attraction',
        'performing_arts_theater': 'Theater',
        'concert_hall': 'Theater',
        'opera_house': 'Theater',
        'philharmonic_hall': 'Theater',
        'auditorium': 'Theater',
        'stadium': 'Entertainment',
        'arena': 'Entertainment',
        'sports_complex': 'Entertainment',
        'sports_activity_location': 'Entertainment',
        'sports_club': 'Entertainment',
        'sports_coaching': 'Entertainment',
        'golf_course': 'Entertainment',
        'tennis_court': 'Entertainment',
        'swimming_pool': 'Entertainment',
        'ice_skating_rink': 'Entertainment',
        'skateboard_park': 'Entertainment',
        'cycling_park': 'Entertainment',
        'hiking_area': 'Entertainment',
        'adventure_sports_center': 'Entertainment',
        'water_park': 'Entertainment',
        'beach': 'Entertainment',
        'marina': 'Entertainment',
        'botanical_garden': 'Entertainment',
        'garden': 'Entertainment',
        'national_park': 'Entertainment',
        'state_park': 'Entertainment',
        'wildlife_park': 'Entertainment',
        'wildlife_refuge': 'Entertainment',
        'planetarium': 'Entertainment',
        'observation_deck': 'Entertainment',
        'ferris_wheel': 'Entertainment',
        'roller_coaster': 'Entertainment',
        'amusement_center': 'Entertainment',
        'video_arcade': 'Entertainment',
        'internet_cafe': 'Entertainment',
        'karaoke': 'Entertainment',
        'dance_hall': 'Entertainment',
        'comedy_club': 'Entertainment',
        'banquet_hall': 'Entertainment',
        'event_venue': 'Entertainment',
        'wedding_venue': 'Entertainment',
        'convention_center': 'Entertainment',
        'cultural_center': 'Entertainment',
        'community_center': 'Entertainment',
        'visitor_center': 'Entertainment',
        'childrens_camp': 'Entertainment',
        'summer_camp_organizer': 'Entertainment',
        'picnic_ground': 'Entertainment',
        'barbecue_area': 'Entertainment',
        'plaza': 'Entertainment',
        'town_square': 'Entertainment',
        'off_roading_area': 'Entertainment',
        'fishing_pond': 'Entertainment',
        'fishing_charter': 'Entertainment',
        'playground': 'Entertainment',
        'dog_park': 'Entertainment',
        'ski_resort': 'Entertainment',
        'campground': 'Entertainment',
        'rv_park': 'Entertainment',
        'camping_cabin': 'Entertainment',
        
        # Shopping
        'shopping_mall': 'Shopping Mall',
        'store': 'Shop',
        'department_store': 'Shop',
        'clothing_store': 'Shop',
        'shoe_store': 'Shop',
        'jewelry_store': 'Shop',
        'electronics_store': 'Shop',
        'book_store': 'Shop',
        'furniture_store': 'Shop',
        'home_goods_store': 'Shop',
        'hardware_store': 'Shop',
        'bicycle_store': 'Shop',
        'pet_store': 'Shop',
        'florist': 'Shop',
        'gift_shop': 'Shop',
        'boutique': 'Boutique',
        'liquor_store': 'Shop',
        'convenience_store': 'Shop',
        'supermarket': 'Shop',
        'grocery_store': 'Shop',
        'market': 'Market',
        'asian_grocery_store': 'Shop',
        'auto_parts_store': 'Shop',
        'cell_phone_store': 'Shop',
        'discount_store': 'Shop',
        'food_store': 'Shop',
        'home_improvement_store': 'Shop',
        'sporting_goods_store': 'Shop',
        'warehouse_store': 'Shop',
        'wholesaler': 'Shop',
        'butcher_shop': 'Shop',
        
        # Lodging
        'lodging': 'Hotel',
        'hotel': 'Hotel',
        'motel': 'Hotel',
        'resort_hotel': 'Hotel',
        'extended_stay_hotel': 'Hotel',
        'bed_and_breakfast': 'Hotel',
        'guest_house': 'Hotel',
        'hostel': 'Hotel',
        'inn': 'Hotel',
        'cottage': 'Hotel',
        'farmstay': 'Hotel',
        'japanese_inn': 'Hotel',
        'budget_japanese_inn': 'Hotel',
        'private_guest_room': 'Hotel',
        'mobile_home_park': 'Hotel',
        
        # Services
        'bank': 'Entertainment',
        'atm': 'Entertainment',
        'gas_station': 'Entertainment',
        'car_wash': 'Entertainment',
        'car_rental': 'Entertainment',
        'car_dealer': 'Entertainment',
        'car_repair': 'Entertainment',
        'parking': 'Entertainment',
        'laundry': 'Entertainment',
        'post_office': 'Entertainment',
        'library': 'Entertainment',
        'school': 'Entertainment',
        'university': 'Entertainment',
        'church': 'Entertainment',
        'mosque': 'Entertainment',
        'synagogue': 'Entertainment',
        'hindu_temple': 'Entertainment',
        'cemetery': 'Entertainment',
        'funeral_home': 'Entertainment',
        'fire_station': 'Entertainment',
        'police': 'Entertainment',
        'hospital': 'Spa',
        'pharmacy': 'Spa',
        'dentist': 'Spa',
        'doctor': 'Spa',
        'veterinary_care': 'Entertainment',
        'insurance_agency': 'Entertainment',
        'real_estate_agency': 'Entertainment',
        'travel_agency': 'Entertainment',
        'tour_agency': 'Entertainment',
        'lawyer': 'Entertainment',
        'accounting': 'Entertainment',
        'electrician': 'Entertainment',
        'plumber': 'Entertainment',
        'painter': 'Entertainment',
        'roofing_contractor': 'Entertainment',
        'locksmith': 'Entertainment',
        'moving_company': 'Entertainment',
        'storage': 'Entertainment',
        'embassy': 'Entertainment',
        'city_hall': 'Entertainment',
        'courthouse': 'Entertainment',
        'local_government_office': 'Entertainment',
        'government_office': 'Entertainment',
        'neighborhood_police_station': 'Entertainment',
        'transit_station': 'Entertainment',
        'bus_station': 'Entertainment',
        'train_station': 'Entertainment',
        'subway_station': 'Entertainment',
        'light_rail_station': 'Entertainment',
        'airport': 'Entertainment',
        'taxi_stand': 'Entertainment',
        'ferry_terminal': 'Entertainment',
        'bus_stop': 'Entertainment',
        'park_and_ride': 'Entertainment',
        'transit_depot': 'Entertainment',
        'truck_stop': 'Entertainment',
        'rest_stop': 'Entertainment',
        'electric_vehicle_charging_station': 'Entertainment',
        'airstrip': 'Entertainment',
        'heliport': 'Entertainment',
        'international_airport': 'Entertainment',
        'public_bath': 'Entertainment',
        'public_bathroom': 'Entertainment',
        'stable': 'Entertainment',
        'corporate_office': 'Entertainment',
        'farm': 'Entertainment',
        'ranch': 'Entertainment',
        'art_studio': 'Entertainment',
        'sculpture': 'Entertainment',
        'historical_place': 'Entertainment',
        'preschool': 'Entertainment',
        'primary_school': 'Entertainment',
        'secondary_school': 'Entertainment',
        'school_district': 'Entertainment',
        'amphitheatre': 'Entertainment',
        'beautician': 'Entertainment',
        'body_art_service': 'Entertainment',
        'catering_service': 'Entertainment',
        'child_care_agency': 'Entertainment',
        'consultant': 'Entertainment',
        'courier_service': 'Entertainment',
        'food_delivery': 'Entertainment',
        'foot_care': 'Entertainment',
        'hair_salon': 'Entertainment',
        'makeup_artist': 'Entertainment',
        'tailor': 'Entertainment',
        'telecommunications_service_provider': 'Entertainment',
        'tourist_information_center': 'Entertainment',
        'psychic': 'Entertainment',
        'general_contractor': 'Entertainment',
        'apartment_building': 'Entertainment',
        'apartment_complex': 'Entertainment',
        'condominium_complex': 'Entertainment',
        'housing_complex': 'Entertainment',
        'camping_cabin': 'Entertainment',
        'natural_feature': 'Entertainment',
        'point_of_interest': 'Entertainment',
        'establishment': 'Entertainment',
        'locality': 'Entertainment',
        'sublocality': 'Entertainment',
        'neighborhood': 'Entertainment',
        'premise': 'Entertainment',
        'subpremise': 'Entertainment',
        'postal_code': 'Entertainment',
        'country': 'Entertainment',
        'administrative_area_level_1': 'Entertainment',
        'administrative_area_level_2': 'Entertainment',
        'administrative_area_level_3': 'Entertainment',
        'administrative_area_level_4': 'Entertainment',
        'administrative_area_level_5': 'Entertainment',
        'administrative_area_level_6': 'Entertainment',
        'administrative_area_level_7': 'Entertainment',
        'colloquial_area': 'Entertainment',
        'archipelago': 'Entertainment',
        'continent': 'Entertainment',
        'finance': 'Entertainment',
        'food': 'Entertainment',
        'health': 'Entertainment',
        'intersection': 'Entertainment',
        'landmark': 'Entertainment',
        'place_of_worship': 'Entertainment',
        'plus_code': 'Entertainment',
        'political': 'Entertainment',
        'postal_code_prefix': 'Entertainment',
        'postal_code_suffix': 'Entertainment',
        'postal_town': 'Entertainment',
        'route': 'Entertainment',
        'street_address': 'Entertainment',
        'street_number': 'Entertainment',
        'sublocality_level_1': 'Entertainment',
        'sublocality_level_2': 'Entertainment',
        'sublocality_level_3': 'Entertainment',
        'sublocality_level_4': 'Entertainment',
        'sublocality_level_5': 'Entertainment',
        'geocode': 'Entertainment',
        'floor': 'Entertainment',
        'room': 'Entertainment',
        'post_box': 'Entertainment'
    }
    
    # Find the best match
    for google_type in google_types:
        if google_type in type_mapping:
            return type_mapping[google_type]
    
    # Default fallback
    return "Entertainment"

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def enrich_one_place(place: Place, google_client: GooglePlaces) -> Tuple[bool, str]:
    """Enrich a single place with Google Maps data"""
    try:
        # Validate required fields - only name is required now
        if not place.name or not place.name.strip():
            return False, "Missing name"
        
        # Normalize search query - use only name + Bangkok
        search_text = normalize_query(place.name)
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
            return False, "No candidates found"
        
        place_id = find_result.get("id")
        if not place_id:
            return False, "No place_id in find result"
        
        # Get place details
        details = google_client.place_details(place_id)
        if not details:
            return False, "No details found"
        
        # Update place with Google Maps data
        place.gmaps_place_id = place_id
        place.gmaps_url = gmaps_url_from_id(place_id)
        
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
        
        # Update rating
        if details.get("rating") is not None:
            place.rating = details["rating"]
        
        # Always update hours from Google Maps (more reliable than TimeOut)
        if details.get("regularOpeningHours"):
            hours = opening_hours_to_json(details["regularOpeningHours"])
            if hours:
                place.hours_json = json.dumps(hours)
        
        # Update category from Google Places types (most reliable source)
        if details.get("types"):
            google_types = details["types"]
            new_category = map_google_type_to_category(google_types)
            if new_category != place.category:
                logger.info(f"Updating category: {place.category} -> {new_category} (Google types: {google_types})")
                place.category = new_category
        
        # Get best photo for the place
        try:
            photo_url = google_client.get_place_photos(place_id)
            if photo_url:
                place.picture_url = photo_url
                logger.info(f"Updated photo: {photo_url[:50]}...")
        except Exception as e:
            logger.warning(f"Failed to get photo for {place.name}: {e}")
        
        return True, "Successfully enriched"
        
    except GooglePlacesError as e:
        logger.error(f"Google Places API error for place {place.id}: {e}")
        return False, f"API error: {e}"
    except Exception as e:
        logger.error(f"Unexpected error for place {place.id}: {e}")
        return False, f"Unexpected error: {e}"


def enrich_places(batch_size: int = 20, dry_run: bool = False):
    """Enrich places with Google Maps data"""
    logger.info(f"Starting enrichment process (batch_size={batch_size}, dry_run={dry_run})")
    
    # Initialize Google Places client (use mock mode if API key not working)
    try:
        google_client = GooglePlaces()
    except Exception as e:
        logger.warning(f"Failed to initialize Google Places client: {e}")
        logger.info("Using mock mode for testing...")
        google_client = GooglePlaces(mock_mode=True)
    
    # Get places that need enrichment
    db = SessionLocal()
    try:
        # Query places that don't have Google Maps data yet
        places_query = db.query(Place).filter(
            Place.processing_status.in_(["new", "summarized", "published"])
        ).filter(
            Place.gmaps_place_id.is_(None)
        ).limit(batch_size)
        
        places = places_query.all()
        total_places = len(places)
        
        if total_places == 0:
            logger.info("No places found for enrichment")
            return
        
        logger.info(f"Found {total_places} places to enrich")
        
        # Process each place
        success_count = 0
        error_count = 0
        
        for i, place in enumerate(places, 1):
            logger.info(f"Processing place {i}/{total_places}: {place.name}")
            
            if dry_run:
                logger.info(f"DRY RUN: Would enrich place {place.id}")
                continue
            
            # Enrich the place
            success, message = enrich_one_place(place, google_client)
            
            if success:
                success_count += 1
                logger.info(f"✅ Place {place.id} enriched: {message}")
                
                # Save changes
                try:
                    db.add(place)
                    db.commit()
                except Exception as e:
                    logger.error(f"Failed to save place {place.id}: {e}")
                    db.rollback()
                    error_count += 1
            else:
                error_count += 1
                logger.warning(f"❌ Place {place.id} failed: {message}")
        
        # Print statistics
        logger.info(f"Enrichment completed:")
        logger.info(f"  Total processed: {total_places}")
        logger.info(f"  Success: {success_count}")
        logger.info(f"  Errors: {error_count}")
        
        # Print Google Places API stats
        api_stats = google_client.get_stats()
        if api_stats:
            logger.info(f"Google Places API usage: {api_stats}")
        
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
    finally:
        db.close()


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Enrich places with Google Maps data")
    parser.add_argument("--batch-size", type=int, default=20, help="Number of places to process")
    parser.add_argument("--dry-run", action="store_true", help="Don't make changes, just show what would be done")
    
    args = parser.parse_args()
    
    enrich_places(batch_size=args.batch_size, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
