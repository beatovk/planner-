#!/usr/bin/env python3
"""
Массовый парсинг TimeOut Bangkok статей
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.core.db import SessionLocal
from enhanced_timeout_adapter import EnhancedTimeOutAdapter as TimeOutAdapter
from apps.places.models import Place
from sqlalchemy import func
import time

# Список ссылок для парсинга
TIMEOUT_URLS = [
    "https://www.timeout.com/bangkok/restaurants/bangkoks-top-10-spots-for-health-conscious-dining",
    "https://www.timeout.com/bangkok/restaurants/best-breakfast-restaurants-in-bangkok",
    "https://www.timeout.com/bangkok/restaurants/bangkoks-best-garden-cafes",
    "https://www.timeout.com/bangkok/restaurants/best-juice-bars-around-bangkok-to-beat-the-heat",
    "https://www.timeout.com/bangkok/shopping/bookstores-cafe-coffee",
    "https://www.timeout.com/bangkok/news/thailand-leads-asias-50-best-restaurants-2025-032625",
    "https://www.timeout.com/bangkok/news/haoma-sustainable-indian-dining-thats-mighty-fine-042325",
    "https://www.timeout.com/bangkok/news/review-what-to-expect-from-the-shake-shack-x-potong-collab-051525",
    "https://www.timeout.com/bangkok/bakery-shops",
    "https://www.timeout.com/bangkok/restaurants/best-bakeries-to-find-perfect-sourdough-bread",
    "https://www.timeout.com/bangkok/restaurants/best-donut-shops-in-bangkok",
    "https://www.timeout.com/bangkok/restaurants/best-restaurants-and-cafes-asoke",
    "https://www.timeout.com/bangkok/restaurants/best-places-to-eat-iconsiam",
    "https://www.timeout.com/bangkok/restaurants/best-restaurants-ari",
    "https://www.timeout.com/bangkok/restaurants/best-restaurants-charoenkrung",
    "https://www.timeout.com/bangkok/best-restaurants-and-cafes-in-soi-sukhumvit-31"
]

def get_existing_places():
    """Получить существующие места для проверки дубликатов"""
    db = SessionLocal()
    try:
        places = db.query(Place.name, Place.source_url).all()
        return {(p.name.lower().strip(), p.source_url) for p in places}
    finally:
        db.close()

def save_places(places_data):
    """Сохранить места в базу данных"""
    db = SessionLocal()
    try:
        existing_places = get_existing_places()
        new_count = 0
        duplicate_count = 0
        
        for place_data in places_data:
            # Проверка на дубликаты по названию
            name_key = place_data['title'].lower().strip()
            source_url = place_data['detail_url'] or f"timeout_{place_data['title'].replace(' ', '_')}"
            
            if (name_key, source_url) in existing_places:
                duplicate_count += 1
                print(f"  Дубликат: {place_data['title']}")
                continue
            
            # Создание нового места
            place = Place(
                name=place_data['title'],
                description_full=place_data.get('description_full'),
                category=place_data.get('category'),
                address=place_data.get('address'),
                hours_json=place_data.get('hours_text'),
                lat=place_data.get('lat'),
                lng=place_data.get('lng'),
                picture_url=place_data.get('picture_url'),
                source='timeout',
                source_url=source_url,
                processing_status='new',
                raw_payload=str(place_data)
            )
            
            db.add(place)
            new_count += 1
            print(f"  Новое место: {place_data['title']}")
        
        db.commit()
        return new_count, duplicate_count
        
    except Exception as e:
        db.rollback()
        print(f"Ошибка при сохранении: {e}")
        return 0, 0
    finally:
        db.close()

def main():
    print("🚀 Запуск массового парсинга TimeOut Bangkok...")
    print(f"📋 Всего ссылок: {len(TIMEOUT_URLS)}")
    print("=" * 60)
    
    adapter = TimeOutAdapter()
    total_new = 0
    total_duplicates = 0
    
    for i, url in enumerate(TIMEOUT_URLS, 1):
        print(f"\n📄 Обрабатываем {i}/{len(TIMEOUT_URLS)}: {url}")
        
        try:
            # Парсинг списка мест
            places_data = adapter.parse_list_page(url)
            print(f"  Найдено мест: {len(places_data)}")
            
            if places_data:
                # Сохранение в базу
                new_count, duplicate_count = save_places(places_data)
                total_new += new_count
                total_duplicates += duplicate_count
                print(f"  ✅ Сохранено новых: {new_count}, дубликатов: {duplicate_count}")
            else:
                print("  ⚠️  Места не найдены")
                
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
        
        # Пауза между запросами
        if i < len(TIMEOUT_URLS):
            print("  ⏳ Пауза 2 секунды...")
            time.sleep(2)
    
    print("\n" + "=" * 60)
    print("📊 ИТОГОВАЯ СТАТИСТИКА:")
    print(f"  Всего обработано ссылок: {len(TIMEOUT_URLS)}")
    print(f"  Новых мест добавлено: {total_new}")
    print(f"  Дубликатов пропущено: {total_duplicates}")
    
    # Финальная статистика по базе
    db = SessionLocal()
    try:
        total_places = db.query(Place).count()
        new_places = db.query(Place).filter(Place.processing_status == 'new').count()
        print(f"  Всего мест в базе: {total_places}")
        print(f"  Мест со статусом 'new': {new_places}")
    finally:
        db.close()
    
    print("\n✅ Массовый парсинг завершен!")

if __name__ == "__main__":
    main()
