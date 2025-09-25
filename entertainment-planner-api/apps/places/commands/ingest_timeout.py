#!/usr/bin/env python3
"""
Команда для ингестии данных из TimeOut Bangkok
"""
import sys
import os
from datetime import datetime
from typing import List

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy.orm import Session
from apps.core.db import SessionLocal
from apps.places.models import Place
from apps.places.ingestion.timeout_adapter import TimeOutAdapter
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def ingest_timeout_places(list_url: str, limit: int = None) -> int:
    """
    Ингестия мест из TimeOut Bangkok
    
    Args:
        list_url: URL страницы списка TimeOut
        limit: Максимальное количество мест для парсинга (None = все)
    
    Returns:
        Количество успешно добавленных мест
    """
    adapter = TimeOutAdapter()
    db = SessionLocal()
    
    try:
        logger.info(f"Начинаем ингестию из TimeOut: {list_url}")
        
        # Парсим места
        places_data = adapter.parse_places_from_list(list_url)
        
        if limit:
            places_data = places_data[:limit]
        
        logger.info(f"Спарсено {len(places_data)} мест")
        
        added_count = 0
        skipped_count = 0
        
        for place_data in places_data:
            try:
                # Проверяем, не существует ли уже место с таким source_url
                existing = db.query(Place).filter(
                    Place.source_url == place_data['source_url']
                ).first()
                
                if existing:
                    logger.info(f"Место уже существует: {place_data['name']}")
                    skipped_count += 1
                    continue
                
                # Создаем новое место
                place = Place(
                    source=place_data['source'],
                    source_url=place_data['source_url'],
                    raw_payload=place_data.get('raw_payload'),
                    scraped_at=datetime.fromtimestamp(place_data['scraped_at']),
                    
                    # Координаты (пока None)
                    lat=place_data.get('lat'),
                    lng=place_data.get('lng'),
                    address=place_data.get('address'),
                    gmaps_place_id=place_data.get('gmaps_place_id'),
                    gmaps_url=place_data.get('gmaps_url'),
                    
                    # Чистые поля
                    name=place_data.get('name'),
                    category=place_data.get('category'),
                    description_full=place_data.get('description_full'),
                    summary=place_data.get('summary'),  # Будет заполнено GPT позже
                    tags_csv=place_data.get('tags_csv'),  # Будет заполнено GPT позже
                    price_level=place_data.get('price_level'),
                    hours_json=place_data.get('hours_text'),  # Пока как текст, потом структурируем
                    picture_url=place_data.get('picture_url'),
                    
                    # Статус обработки
                    processing_status='new'  # Будет обработано GPT позже
                )
                
                db.add(place)
                added_count += 1
                
                logger.info(f"Добавлено место: {place_data['name']}")
                
            except Exception as e:
                logger.error(f"Ошибка при добавлении места {place_data.get('name', 'Unknown')}: {e}")
                continue
        
        db.commit()
        
        logger.info(f"Ингестия завершена:")
        logger.info(f"- Добавлено новых мест: {added_count}")
        logger.info(f"- Пропущено существующих: {skipped_count}")
        
        return added_count
        
    except Exception as e:
        logger.error(f"Ошибка ингестии: {e}")
        db.rollback()
        return 0
    finally:
        db.close()


def main():
    """Главная функция команды"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Ингестия мест из TimeOut Bangkok')
    parser.add_argument('url', help='URL страницы списка TimeOut')
    parser.add_argument('--limit', type=int, help='Максимальное количество мест')
    parser.add_argument('--test', action='store_true', help='Тестовый режим (только парсинг)')
    
    args = parser.parse_args()
    
    if args.test:
        # Тестовый режим - только парсинг без сохранения
        logger.info("Тестовый режим - только парсинг")
        adapter = TimeOutAdapter()
        places = adapter.parse_places_from_list(args.url)
        
        print(f"\nНайдено мест: {len(places)}")
        for i, place in enumerate(places[:5], 1):  # Показываем первые 5
            print(f"\n--- Место {i} ---")
            print(f"Название: {place.get('name')}")
            print(f"Категория: {place.get('category')}")
            print(f"Адрес: {place.get('address')}")
            print(f"Часы: {place.get('hours_text')}")
            print(f"Картинка: {place.get('picture_url')}")
    else:
        # Обычный режим - парсинг и сохранение
        added_count = ingest_timeout_places(args.url, args.limit)
        print(f"Добавлено мест: {added_count}")


if __name__ == "__main__":
    main()
