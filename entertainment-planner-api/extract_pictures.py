#!/usr/bin/env python3
"""
Скрипт для извлечения URL картинок и сохранения в файл
"""
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from apps.core.db import Base
from apps.places.models import Place
from apps.places.ingestion.timeout_adapter import TimeOutAdapter
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://ep:ep@localhost:5432/ep")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def extract_pictures():
    db = SessionLocal()
    adapter = TimeOutAdapter()
    
    # Получаем места без картинок
    places_without_pictures = db.query(Place).filter(
        Place.picture_url.is_(None),
        Place.source_url.like('%timeout.com%'),
        Place.processing_status == 'summarized'
    ).limit(50).all()
    
    logger.info(f"Найдено {len(places_without_pictures)} мест без картинок")

    results = []
    for place in places_without_pictures:
        if not place.source_url:
            logger.warning(f"Место {place.name} (ID: {place.id}) не имеет source_url, пропускаем.")
            continue

        logger.info(f"Обрабатываем: {place.name}")
        try:
            # Re-parse the detail page to get the image URL
            parsed_data = adapter.parse_detail_page(place.source_url)
            if parsed_data and parsed_data.get('picture_url'):
                results.append({
                    'id': place.id,
                    'name': place.name,
                    'picture_url': parsed_data['picture_url']
                })
                logger.info(f"✅ Найдена картинка для {place.name}: {parsed_data['picture_url']}")
            else:
                logger.info(f"❌ Не удалось найти картинку для {place.name} по URL: {place.source_url}")
        except Exception as e:
            logger.error(f"Ошибка для {place.name}: {e}")
    
    db.close()
    
    # Сохраняем результаты в файл
    with open('picture_urls.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Найдено {len(results)} картинок, сохранено в picture_urls.json")

if __name__ == "__main__":
    extract_pictures()
