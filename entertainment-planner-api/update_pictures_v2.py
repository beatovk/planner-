#!/usr/bin/env python3
"""
Скрипт для обновления картинок мест без picture_url
Использует SQLAlchemy и TimeOutAdapter
"""
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from apps.core.db import Base
from apps.places.models import Place
from apps.places.ingestion.timeout_adapter import TimeOutAdapter
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = "sqlite:///./entertainment.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def update_place_pictures():
    db = SessionLocal()
    adapter = TimeOutAdapter()
    
    # Получаем места без картинок
    places_without_pictures = db.query(Place).filter(
        Place.picture_url.is_(None),
        Place.source_url.like('%timeout.com%'),
        Place.processing_status == 'summarized'
    ).limit(50).all()
    
    logger.info(f"Найдено {len(places_without_pictures)} мест без картинок")

    updated_count = 0
    for place in places_without_pictures:
        if not place.source_url:
            logger.warning(f"Место {place.name} (ID: {place.id}) не имеет source_url, пропускаем.")
            continue

        logger.info(f"Обрабатываем: {place.name}")
        try:
            # Re-parse the detail page to get the image URL
            parsed_data = adapter.parse_detail_page(place.source_url)
            if parsed_data and parsed_data.get('picture_url'):
                place.picture_url = parsed_data['picture_url']
                db.add(place)
                db.commit()
                db.refresh(place)
                updated_count += 1
                logger.info(f"✅ Обновлена картинка для {place.name}: {place.picture_url}")
            else:
                logger.info(f"❌ Не удалось найти картинку для {place.name} по URL: {place.source_url}")
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка для {place.name}: {e}")
    
    db.close()
    logger.info(f"Обновлено {updated_count} мест")

if __name__ == "__main__":
    update_place_pictures()
