#!/usr/bin/env python3
"""
Массовое обогащение цен через Google Places API.
Ищем места без price_level и пытаемся найти их через Google Places API.
"""

import time
from apps.core.db import SessionLocal
from apps.places.models import Place
from apps.places.services.google_places import GooglePlaces
from sqlalchemy import and_, or_

def enrich_prices_google(batch_size=50, max_places=200):
    """
    Обогащает цены через Google Places API для мест без price_level.
    """
    db = SessionLocal()
    google_client = GooglePlaces()
    
    try:
        # Находим места без price_level, но с gmaps_place_id
        places = db.query(Place).filter(
            and_(
                Place.price_level.is_(None),
                Place.gmaps_place_id.isnot(None),
                Place.gmaps_place_id != ''
            )
        ).limit(max_places).all()
        
        print(f"Найдено {len(places)} мест для обогащения цен")
        
        updated_count = 0
        error_count = 0
        
        for i, place in enumerate(places):
            if i >= max_places:
                break
                
            try:
                print(f"[{i+1}/{len(places)}] Обрабатываем: {place.name}")
                
                # Получаем детали места из Google Places API
                details = google_client.place_details(place.gmaps_place_id)
                
                # Обновляем price_level если найден
                if details.get("priceLevel") is not None:
                    price_level = details["priceLevel"]
                    
                    # Конвертируем строковые price levels в числа
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
                    updated_count += 1
                    print(f"  ✅ Обновлен price_level: {price_level}")
                else:
                    print(f"  ❌ Price level не найден в Google")
                
                # Коммитим каждые batch_size мест
                if (i + 1) % batch_size == 0:
                    db.commit()
                    print(f"  💾 Сохранено {batch_size} мест")
                    time.sleep(1)  # Пауза между батчами
                    
            except Exception as e:
                error_count += 1
                print(f"  ❌ Ошибка для {place.name}: {e}")
                continue
        
        # Финальный коммит
        db.commit()
        
        print(f"\n=== Результаты ===")
        print(f"Обработано мест: {len(places)}")
        print(f"Обновлено цен: {updated_count}")
        print(f"Ошибок: {error_count}")
        print(f"Успешность: {updated_count/len(places)*100:.1f}%")
        
    finally:
        db.close()


def test_specific_places():
    """Тестируем на конкретных местах."""
    test_places = [
        "Gaggan Anand",
        "Le Normandie", 
        "Jay Fai",
        "Thip Samai",
        "Ki Izakaya"
    ]
    
    db = SessionLocal()
    google_client = GooglePlaces()
    
    try:
        for place_name in test_places:
            place = db.query(Place).filter(Place.name.ilike(f'%{place_name}%')).first()
            if place:
                print(f"\n=== {place.name} ===")
                print(f"Place ID: {place.gmaps_place_id}")
                print(f"Текущий price_level: {place.price_level}")
                
                if place.gmaps_place_id:
                    details = google_client.place_details(place.gmaps_place_id)
                    api_price = details.get("priceLevel")
                    print(f"Google API price_level: {api_price}")
                    
                    if api_price and place.price_level is None:
                        # Конвертируем и обновляем
                        if isinstance(api_price, str):
                            price_map = {
                                "PRICE_LEVEL_FREE": 0,
                                "PRICE_LEVEL_INEXPENSIVE": 1,
                                "PRICE_LEVEL_MODERATE": 2,
                                "PRICE_LEVEL_EXPENSIVE": 3,
                                "PRICE_LEVEL_VERY_EXPENSIVE": 4
                            }
                            api_price = price_map.get(api_price, api_price)
                        
                        place.price_level = api_price
                        print(f"✅ Обновлен price_level: {api_price}")
                    else:
                        print("❌ Цена не найдена или уже есть")
            else:
                print(f"❌ Место {place_name} не найдено")
        
        db.commit()
        
    finally:
        db.close()


if __name__ == "__main__":
    print("=== Тест конкретных мест ===")
    test_specific_places()
    
    print("\n=== Массовое обогащение ===")
    enrich_prices_google(batch_size=20, max_places=100)
