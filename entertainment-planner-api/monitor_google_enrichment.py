#!/usr/bin/env python3
"""
Скрипт для мониторинга прогресса Google Places обогащения
"""

import time
import os
import sys
import psycopg
from datetime import datetime, timezone

# Установка PYTHONPATH для корректного импорта
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Загрузка переменных окружения из .env файла
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

DB_URL = os.getenv("DATABASE_URL", "postgresql://ep:ep@localhost:5432/ep")

def get_enrichment_progress():
    """Получает текущий прогресс обогащения мест из БД."""
    conn = None
    try:
        conn = psycopg.connect(DB_URL)
        cursor = conn.cursor()

        # Статистика по новым местам Culture & Arts
        cursor.execute('''
        SELECT 
            COUNT(*) as total_places,
            COUNT(CASE WHEN lat IS NOT NULL AND lng IS NOT NULL THEN 1 END) as with_coords,
            COUNT(CASE WHEN gmaps_place_id IS NOT NULL THEN 1 END) as with_place_id,
            COUNT(CASE WHEN rating IS NOT NULL THEN 1 END) as with_rating,
            COUNT(CASE WHEN address IS NOT NULL THEN 1 END) as with_address,
            COUNT(CASE WHEN website IS NOT NULL THEN 1 END) as with_website,
            COUNT(CASE WHEN phone IS NOT NULL THEN 1 END) as with_phone,
            COUNT(CASE WHEN hours_json IS NOT NULL THEN 1 END) as with_hours
        FROM places 
        WHERE source = 'timeout_bangkok' 
        AND processing_status = 'summarized'
        ''')
        stats = cursor.fetchone()

        # Последние 5 обогащенных мест
        cursor.execute('''
        SELECT name, lat, lng, rating, address, updated_at
        FROM places 
        WHERE source = 'timeout_bangkok' 
        AND processing_status = 'summarized'
        AND lat IS NOT NULL AND lng IS NOT NULL
        ORDER BY updated_at DESC
        LIMIT 5
        ''')
        last_enriched = cursor.fetchall()

        return stats, last_enriched
    except Exception as e:
        print(f"❌ Ошибка при получении прогресса: {e}")
        return None, []
    finally:
        if conn:
            conn.close()

def display_progress():
    """Отображает прогресс в терминале."""
    while True:
        os.system('clear')  # Очищаем терминал
        print("🌍 МОНИТОРИНГ GOOGLE PLACES ОБОГАЩЕНИЯ")
        print("========================================\n")

        stats, last_enriched = get_enrichment_progress()
        
        if stats is None:
            print("❌ Ошибка получения данных")
            time.sleep(5)
            continue

        total_places, with_coords, with_place_id, with_rating, with_address, with_website, with_phone, with_hours = stats

        print(f"🎨 Всего мест Culture & Arts: {total_places}")
        print(f"📍 С координатами: {with_coords}/{total_places} ({with_coords/total_places*100:.1f}%)")
        print(f"🆔 С Place ID: {with_place_id}/{total_places} ({with_place_id/total_places*100:.1f}%)")
        print(f"⭐ С рейтингом: {with_rating}/{total_places} ({with_rating/total_places*100:.1f}%)")
        print(f"🏠 С адресом: {with_address}/{total_places} ({with_address/total_places*100:.1f}%)")
        print(f"🌐 С веб-сайтом: {with_website}/{total_places} ({with_website/total_places*100:.1f}%)")
        print(f"📞 С телефоном: {with_phone}/{total_places} ({with_phone/total_places*100:.1f}%)")
        print(f"🕒 С часами работы: {with_hours}/{total_places} ({with_hours/total_places*100:.1f}%)")

        if last_enriched:
            print(f"\n🎯 ПОСЛЕДНИЕ ОБОГАЩЕННЫЕ МЕСТА:")
            for name, lat, lng, rating, address, updated_at in last_enriched:
                print(f"  - {name}")
                print(f"    📍 {lat:.6f}, {lng:.6f}")
                print(f"    ⭐ {rating}/5.0" if rating else "    ⭐ Нет рейтинга")
                print(f"    🏠 {address[:50]}..." if address else "    🏠 Нет адреса")
                print(f"    🕒 {updated_at.strftime('%H:%M:%S')}")
                print()
        else:
            print("\nНет обогащенных мест.")

        print(f"\nОбновление каждые 3 секунды... (Ctrl+C для выхода)")
        time.sleep(3)

if __name__ == "__main__":
    display_progress()
