#!/usr/bin/env python3
"""
Скрипт для обогащения мест без слов в скобках
"""

import os
import sys
import psycopg
import re
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from apps.places.services.google_places import GooglePlaces

def clean_name(name):
    """Убирает слова в скобках из названия"""
    # Убираем все в скобках
    cleaned = re.sub(r'\s*\([^)]*\)', '', name)
    # Убираем лишние пробелы
    cleaned = cleaned.strip()
    return cleaned

def enrich_places_without_brackets():
    """Обогащение мест через Google Places API без слов в скобках"""
    
    print("🌍 Обогащение мест без слов в скобках...")
    
    # Подключаемся к БД
    conn = psycopg.connect('postgresql://ep:ep@localhost:5432/ep')
    cursor = conn.cursor()
    
    try:
        # Получаем места без Google данных
        cursor.execute('''
        SELECT id, name, category
        FROM places 
        WHERE source = 'timeout_bangkok' 
        AND processing_status = 'summarized'
        AND (lat IS NULL OR gmaps_place_id IS NULL)
        ORDER BY name
        ''')
        places = cursor.fetchall()
        
        print(f"🔍 Найдено {len(places)} мест для обогащения")
        
        if not places:
            print("✅ Все места уже обогащены!")
            return
        
        # Инициализируем Google Places сервис
        google_service = GooglePlaces()
        
        updated_count = 0
        error_count = 0
        
        for i, (place_id, name, category) in enumerate(places, 1):
            print(f"🔄 {i}/{len(places)}: {name}")
            
            # Очищаем название от слов в скобках
            clean_name_str = clean_name(name)
            print(f"   🧹 Очищенное название: '{clean_name_str}'")
            
            try:
                # Ищем место через Google Places API с очищенным названием
                search_result = google_service.find_place(f"{clean_name_str} Bangkok")
                
                if search_result and 'place_id' in search_result:
                    place_id_google = search_result['place_id']
                    print(f"   🔍 Найдено в Google: {search_result.get('name', 'N/A')}")
                    
                    # Получаем детали места
                    place_details = google_service.place_details(place_id_google)
                    
                    if place_details:
                        # Обновляем только основные поля без price_level
                        cursor.execute('''
                        UPDATE places 
                        SET lat = %s, lng = %s, address = %s, 
                            gmaps_place_id = %s, gmaps_url = %s,
                            business_status = %s, utc_offset_minutes = %s,
                            category = %s, rating = %s, picture_url = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        ''', (
                            place_details.get('lat'),
                            place_details.get('lng'),
                            place_details.get('formatted_address'),
                            place_id_google,
                            f"https://www.google.com/maps/place/?q=place_id:{place_id_google}",
                            place_details.get('business_status'),
                            place_details.get('utc_offset'),
                            place_details.get('types', [category])[0] if place_details.get('types') else category,
                            place_details.get('rating'),
                            place_details.get('photo_reference'),
                            place_id
                        ))
                        
                        print(f"   ✅ Обогащено: {place_details.get('rating', 'N/A')}/5.0")
                        updated_count += 1
                    else:
                        print(f"   ⚠️ Детали не найдены")
                        error_count += 1
                else:
                    print(f"   ❌ Место не найдено в Google Places")
                    error_count += 1
                
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
                error_count += 1
                continue
        
        # Коммитим изменения
        conn.commit()
        
        print(f"\\n📊 РЕЗУЛЬТАТЫ:")
        print(f"✅ Обновлено: {updated_count} мест")
        print(f"❌ Ошибок: {error_count} мест")
        print(f"📈 Успешность: {updated_count/(updated_count+error_count)*100:.1f}%")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Критическая ошибка: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    # Проверяем API ключ
    if not os.getenv('GOOGLE_MAPS_API_KEY'):
        print("❌ Ошибка: GOOGLE_MAPS_API_KEY не найден в переменных окружения")
        sys.exit(1)
    
    print("🔑 Google Maps API ключ: установлен")
    print("-" * 50)
    
    enrich_places_without_brackets()
