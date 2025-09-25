#!/usr/bin/env python3
"""
Простой скрипт для проверки прогресса Google обогащения
"""

import psycopg
import time

def check_progress():
    conn = psycopg.connect('postgresql://ep:ep@localhost:5432/ep')
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT 
        COUNT(*) as total_places,
        COUNT(CASE WHEN lat IS NOT NULL AND lng IS NOT NULL THEN 1 END) as with_coords,
        COUNT(CASE WHEN gmaps_place_id IS NOT NULL THEN 1 END) as with_place_id,
        COUNT(CASE WHEN rating IS NOT NULL THEN 1 END) as with_rating,
        COUNT(CASE WHEN address IS NOT NULL THEN 1 END) as with_address
    FROM places 
    WHERE source = 'timeout_bangkok' 
    AND processing_status = 'summarized'
    ''')
    stats = cursor.fetchone()
    
    total, coords, place_id, rating, address = stats
    remaining = total - coords
    
    print(f"🎨 Culture & Arts места: {coords}/{total} обогащены ({coords/total*100:.1f}%)")
    print(f"📍 Координаты: {coords}")
    print(f"🆔 Place ID: {place_id}")
    print(f"⭐ Рейтинг: {rating}")
    print(f"🏠 Адрес: {address}")
    print(f"❌ Осталось: {remaining} мест")
    
    conn.close()
    return remaining

if __name__ == "__main__":
    while True:
        print("\\n" + "="*50)
        remaining = check_progress()
        if remaining == 0:
            print("\\n🎉 Все места обогащены!")
            break
        print("\\nОбновление через 10 секунд...")
        time.sleep(10)
