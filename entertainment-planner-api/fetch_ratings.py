#!/usr/bin/env python3
"""
Скрипт для получения рейтингов мест через Google Places API
"""

import os
import sys
import time
import psycopg
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from apps.places.services.google_places import GooglePlaces

def fetch_ratings():
    """Получение рейтингов для мест без рейтинга"""
    
    print("⭐ Получение рейтингов через Google Places API...")
    
    # Подключаемся к БД
    conn = psycopg.connect('postgresql://ep:ep@localhost:5432/ep')
    cursor = conn.cursor()
    
    try:
        # Получаем места без рейтинга
        cursor.execute('''
        SELECT id, name, gmaps_place_id, lat, lng
        FROM places 
        WHERE description_full IS NOT NULL 
        AND description_full != '' 
        AND description_full != 'N/A'
        AND processing_status = 'summarized'
        AND rating IS NULL
        AND gmaps_place_id IS NOT NULL
        ORDER BY name
        ''')
        places = cursor.fetchall()
        
        print(f"🔍 Найдено {len(places)} мест без рейтинга")
        
        if not places:
            print("✅ Все места уже имеют рейтинги!")
            return
        
        # Инициализируем Google Places сервис
        google_service = GooglePlaces()
        
        updated_count = 0
        error_count = 0
        
        for i, (place_id, name, gmaps_place_id, lat, lng) in enumerate(places, 1):
            print(f"🔄 {i}/{len(places)}: {name}")
            
            try:
                # Получаем детали места через Google Places API
                place_details = google_service.place_details(gmaps_place_id)
                
                if place_details and 'rating' in place_details:
                    rating = place_details['rating']
                    user_ratings_total = place_details.get('user_ratings_total', 0)
                    
                    # Обновляем рейтинг в БД
                    cursor.execute('''
                    UPDATE places 
                    SET rating = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    ''', (rating, place_id))
                    
                    print(f"   ✅ Рейтинг: {rating}/5.0 ({user_ratings_total} отзывов)")
                    updated_count += 1
                else:
                    print(f"   ⚠️ Рейтинг не найден в Google Places")
                    error_count += 1
                
                # Небольшая пауза между запросами
                time.sleep(0.1)
                
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
    
    fetch_ratings()
