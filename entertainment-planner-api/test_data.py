#!/usr/bin/env python3
"""
Скрипт для создания тестовых данных в новой схеме MVP
"""
import sys
import os
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from apps.core.db import SessionLocal
from apps.places.models import Place


def create_test_places():
    """Создать тестовые места для проверки новой схемы"""
    db = SessionLocal()
    try:
        # Проверяем, есть ли уже данные
        existing_count = db.query(Place).count()
        if existing_count > 0:
            print(f"В базе уже есть {existing_count} записей. Пропускаем создание тестовых данных.")
            return
        
        # Создаем тестовые места
        test_places = [
            {
                "source": "timeout",
                "source_url": "https://timeout.com/bangkok/restaurants/example1",
                "raw_payload": '{"title": "Test Restaurant 1", "description": "Amazing Thai food", "location": "Bangkok"}',
                "scraped_at": datetime.utcnow(),
                "lat": 13.7563,
                "lng": 100.5018,
                "address": "123 Sukhumvit Road, Bangkok",
                "name": "Test Thai Restaurant",
                "category": "food",
                "description_full": "Authentic Thai cuisine with traditional recipes passed down through generations. Famous for their pad thai and tom yum soup.",
                "summary": "Authentic Thai restaurant famous for pad thai",
                "tags_csv": "thai,authentic,pad-thai,tom-yum",
                "price_level": 2,
                "hours_json": '{"monday": "10:00-22:00", "tuesday": "10:00-22:00"}',
                "picture_url": "https://images.unsplash.com/photo-1551218808-94e220e084d2?w=800",
                "processing_status": "published",
                "published_at": datetime.utcnow()
            },
            {
                "source": "timeout",
                "source_url": "https://timeout.com/bangkok/bars/example2",
                "raw_payload": '{"title": "Rooftop Bar", "description": "Amazing city views", "location": "Bangkok"}',
                "scraped_at": datetime.utcnow(),
                "lat": 13.7563,
                "lng": 100.5018,
                "address": "456 Silom Road, Bangkok",
                "name": "Sky Bar Bangkok",
                "category": "bar",
                "description_full": "Luxurious rooftop bar with panoramic views of Bangkok skyline. Perfect for sunset cocktails and romantic dinners.",
                "summary": "Rooftop bar with stunning city views",
                "tags_csv": "rooftop,romantic,sunset,cocktails",
                "price_level": 4,
                "hours_json": '{"monday": "17:00-02:00", "tuesday": "17:00-02:00"}',
                "picture_url": "https://images.unsplash.com/photo-1514933651103-005eec06c04b?w=800",
                "processing_status": "published",
                "published_at": datetime.utcnow()
            },
            {
                "source": "timeout",
                "source_url": "https://timeout.com/bangkok/parks/example3",
                "raw_payload": '{"title": "Lumpini Park", "description": "Green oasis in the city", "location": "Bangkok"}',
                "scraped_at": datetime.utcnow(),
                "lat": 13.7367,
                "lng": 100.5231,
                "address": "Lumpini Park, Bangkok",
                "name": "Lumpini Park",
                "category": "park",
                "description_full": "Large public park in the heart of Bangkok. Features walking paths, lake, outdoor gym, and various recreational activities. Great for morning jogging and evening relaxation.",
                "summary": "Large public park perfect for jogging and relaxation",
                "tags_csv": "park,green,jogging,relaxation,free",
                "price_level": 0,
                "hours_json": '{"monday": "04:30-21:00", "tuesday": "04:30-21:00"}',
                "picture_url": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=800",
                "processing_status": "published",
                "published_at": datetime.utcnow()
            }
        ]
        
        for place_data in test_places:
            place = Place(**place_data)
            db.add(place)
        
        db.commit()
        print(f"Создано {len(test_places)} тестовых мест!")
        
        # Выводим созданные места
        places = db.query(Place).all()
        for place in places:
            print(f"- {place.name} ({place.category}) - {place.processing_status}")
            
    except Exception as e:
        print(f"Ошибка при создании тестовых данных: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_test_places()
