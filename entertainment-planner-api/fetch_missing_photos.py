#!/usr/bin/env python3
"""
Скрипт для получения недостающих фотографий через Google Places API
"""

import os
import sys
import psycopg
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from apps.places.services.google_places import GooglePlaces

def fetch_missing_photos():
    """Получение недостающих фотографий через Google Places API"""
    
    print("📸 Получение недостающих фотографий...")
    
    # Подключаемся к БД
    conn = psycopg.connect('postgresql://ep:ep@localhost:5432/ep')
    cursor = conn.cursor()
    
    try:
        # Получаем места без фотографий, но с Google Place ID
        cursor.execute('''
        SELECT id, name, gmaps_place_id, lat, lng
        FROM places 
        WHERE processing_status = 'summarized'
        AND (picture_url IS NULL OR picture_url = '')
        AND gmaps_place_id IS NOT NULL
        ORDER BY name
        ''')
        places = cursor.fetchall()
        
        print(f"🔍 Найдено {len(places)} мест без фотографий с Google Place ID")
        
        if not places:
            print("✅ Все места уже имеют фотографии!")
            return
        
        # Инициализируем Google Places сервис
        google_service = GooglePlaces()
        
        updated_count = 0
        error_count = 0
        
        for i, (place_id, name, gmaps_place_id, lat, lng) in enumerate(places, 1):
            print(f"🔄 {i}/{len(places)}: {name}")
            
            try:
                # Получаем фотографии через Google Places API
                photo_url = google_service.get_place_photos(gmaps_place_id)
                
                if photo_url:
                    # Обновляем фотографию в БД
                    cursor.execute('''
                    UPDATE places 
                    SET picture_url = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    ''', (photo_url, place_id))
                    
                    print(f"   ✅ Фото получено: {photo_url[:60]}...")
                    updated_count += 1
                else:
                    print(f"   ⚠️ Фотография не найдена")
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
    
    fetch_missing_photos()
