#!/usr/bin/env python3
"""
Временный скрипт для обогащения мест без категорий через Google API
"""

import os
import sys
import time
import psycopg
import json
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv(Path(__file__).parent / '.env')

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from apps.places.services.google_places import GooglePlaces

# Исправляем URL для psycopg
db_url = os.getenv("DATABASE_URL", "postgresql://ep:ep@localhost:5432/ep")
if "+psycopg" in db_url:
    db_url = db_url.replace("+psycopg", "")
DB_URL = db_url

def map_google_type_to_category(google_types: list) -> str:
    """Map Google Places API types to our category system"""
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
        
        # Entertainment & Recreation
        'amusement_park': 'Entertainment',
        'aquarium': 'Entertainment',
        'art_gallery': 'Entertainment',
        'bowling_alley': 'Entertainment',
        'casino': 'Entertainment',
        'movie_theater': 'Entertainment',
        'museum': 'Entertainment',
        'park': 'Entertainment',
        'zoo': 'Entertainment',
        'tourist_attraction': 'Entertainment',
        'spa': 'Entertainment',
        'gym': 'Entertainment',
        'sports_complex': 'Entertainment',
        'stadium': 'Entertainment',
        'theater': 'Entertainment',
        'concert_hall': 'Entertainment',
        'library': 'Entertainment',
        'shopping_mall': 'Entertainment',
        'shopping_center': 'Entertainment',
        'store': 'Entertainment',
        'clothing_store': 'Entertainment',
        'electronics_store': 'Entertainment',
        'book_store': 'Entertainment',
        'jewelry_store': 'Entertainment',
        'shoe_store': 'Entertainment',
        'furniture_store': 'Entertainment',
        'home_goods_store': 'Entertainment',
        'gift_shop': 'Entertainment',
        'toy_store': 'Entertainment',
        'pet_store': 'Entertainment',
        'florist': 'Entertainment',
        'pharmacy': 'Entertainment',
        'supermarket': 'Entertainment',
        'grocery_store': 'Entertainment',
        'convenience_store': 'Entertainment',
        'gas_station': 'Entertainment',
        'atm': 'Entertainment',
        'bank': 'Entertainment',
        'post_office': 'Entertainment',
        'hospital': 'Entertainment',
        'pharmacy': 'Entertainment',
        'veterinary_care': 'Entertainment',
        'dentist': 'Entertainment',
        'doctor': 'Entertainment',
        'lawyer': 'Entertainment',
        'insurance_agency': 'Entertainment',
        'real_estate_agency': 'Entertainment',
        'travel_agency': 'Entertainment',
        'car_rental': 'Entertainment',
        'car_dealer': 'Entertainment',
        'car_repair': 'Entertainment',
        'car_wash': 'Entertainment',
        'parking': 'Entertainment',
        'subway_station': 'Entertainment',
        'bus_station': 'Entertainment',
        'train_station': 'Entertainment',
        'airport': 'Entertainment',
        'lodging': 'Entertainment',
        'rv_park': 'Entertainment',
        'campground': 'Entertainment',
        'place_of_worship': 'Entertainment',
        'cemetery': 'Entertainment',
        'funeral_home': 'Entertainment',
        'city_hall': 'Entertainment',
        'courthouse': 'Entertainment',
        'embassy': 'Entertainment',
        'fire_station': 'Entertainment',
        'local_government_office': 'Entertainment',
        'police': 'Entertainment',
        'school': 'Entertainment',
        'university': 'Entertainment',
        'primary_school': 'Entertainment',
        'secondary_school': 'Entertainment',
        'child_care': 'Entertainment',
        'preschool': 'Entertainment',
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

class CategoryFixer:
    """Агент для исправления категорий через Google API"""
    
    def __init__(self):
        self.google_service = GooglePlaces()
        self.stats = {
            'total_processed': 0,
            'google_enriched': 0,
            'failed': 0
        }
    
    def run(self, batch_size: int = 50):
        """Запускает исправление категорий"""
        print("🚀 ЗАПУСК ИСПРАВЛЕНИЯ КАТЕГОРИЙ")
        print("=" * 50)
        
        while True:
            places = self._get_places_without_categories(batch_size)
            
            if not places:
                print("✅ Все места имеют категории!")
                break
            
            print(f"📊 Найдено {len(places)} мест без категорий")
            
            for i, place in enumerate(places, 1):
                print(f"\n🔄 {i}/{len(places)}: {place['name']}")
                
                success = self._enrich_place_category(place)
                
                if success:
                    self.stats['google_enriched'] += 1
                    print(f"   ✅ Категория обновлена")
                else:
                    self.stats['failed'] += 1
                    print(f"   ❌ Не удалось обогатить")
                
                self.stats['total_processed'] += 1
                
                # Пауза между запросами
                time.sleep(0.5)
            
            self._show_stats()
    
    def _get_places_without_categories(self, batch_size: int):
        """Получает места без категорий"""
        conn = None
        try:
            conn = psycopg.connect(DB_URL)
            cursor = conn.cursor()
            
            # Ищем места без категорий
            cursor.execute('''
                SELECT id, name, category, gmaps_place_id, lat, lng
                FROM places
                WHERE (category IS NULL OR category = '')
                AND processing_status IN ('summarized', 'published', 'enriched')
                ORDER BY updated_at ASC
                LIMIT %s
            ''', (batch_size,))
            
            places = []
            for row in cursor.fetchall():
                places.append({
                    'id': row[0],
                    'name': row[1],
                    'category': row[2],
                    'gmaps_place_id': row[3],
                    'lat': row[4],
                    'lng': row[5]
                })
            
            return places
            
        except Exception as e:
            print(f"❌ Ошибка получения мест: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def _enrich_place_category(self, place: dict) -> bool:
        """Обогащает категорию места через Google API"""
        try:
            # Если у места есть Google Place ID, используем его
            if place.get('gmaps_place_id'):
                place_id = place['gmaps_place_id']
                place_details = self.google_service.place_details(place_id)
                
                if place_details and place_details.get('types'):
                    new_category = map_google_type_to_category(place_details['types'])
                    return self._update_place_category(place['id'], new_category)
            else:
                # Если нет Google Place ID, ищем место
                search_query = f"{place['name']} Bangkok"
                found_place = self.google_service.find_place(search_query)
                
                if found_place and found_place.get('id'):
                    place_id = found_place['id']
                    place_details = self.google_service.place_details(place_id)
                    
                    if place_details and place_details.get('types'):
                        new_category = map_google_type_to_category(place_details['types'])
                        return self._update_place_category(place['id'], new_category)
            
            return False
            
        except Exception as e:
            print(f"   ⚠️ Ошибка Google API: {e}")
            return False
    
    def _update_place_category(self, place_id: int, category: str) -> bool:
        """Обновляет категорию места в БД"""
        conn = None
        try:
            conn = psycopg.connect(DB_URL)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE places
                SET category = %s, updated_at = %s
                WHERE id = %s
            ''', (category, datetime.now(timezone.utc), place_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"   ❌ Ошибка обновления БД: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    def _show_stats(self):
        """Показывает статистику"""
        print(f"\n📊 СТАТИСТИКА:")
        print(f"   Всего обработано: {self.stats['total_processed']}")
        print(f"   Google обогащено: {self.stats['google_enriched']}")
        print(f"   Не удалось: {self.stats['failed']}")

def main():
    """Главная функция"""
    print("🔧 ИСПРАВЛЕНИЕ КАТЕГОРИЙ ЧЕРЕЗ GOOGLE API")
    print("=" * 50)
    
    # Проверяем API ключ
    if not os.getenv('GOOGLE_MAPS_API_KEY'):
        print("❌ Ошибка: GOOGLE_MAPS_API_KEY не найден в переменных окружения")
        sys.exit(1)
    
    print("🔑 Google Maps API ключ: установлен")
    
    # Создаем агент
    fixer = CategoryFixer()
    
    # Запускаем исправление
    fixer.run(batch_size=20)

if __name__ == "__main__":
    main()
