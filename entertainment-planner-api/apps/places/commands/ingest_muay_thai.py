#!/usr/bin/env python3
"""
Команда для ингестии Muay Thai мест из CSV файла
"""
import sys
import os
import csv
import json
from datetime import datetime
from typing import List, Dict, Any

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy.orm import Session
from apps.core.db import SessionLocal
from apps.places.models import Place
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def ingest_muay_thai_places(csv_file_path: str, limit: int = None) -> int:
    """
    Ингестия Muay Thai мест из CSV файла
    
    Args:
        csv_file_path: Путь к CSV файлу
        limit: Максимальное количество мест для обработки (None = все)
    
    Returns:
        Количество успешно добавленных мест
    """
    db = SessionLocal()
    
    try:
        logger.info(f"Начинаем ингестию Muay Thai мест из: {csv_file_path}")
        
        # Читаем CSV файл
        places_data = []
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['name'].strip():  # Пропускаем пустые строки
                    places_data.append({
                        'name': row['name'].strip(),
                        'description_full': row['description_full'].strip(),
                        'source_url': row['source_url'].strip()
                    })
        
        if limit:
            places_data = places_data[:limit]
        
        logger.info(f"Загружено {len(places_data)} мест из CSV")
        
        added_count = 0
        skipped_count = 0
        
        for i, place_data in enumerate(places_data, 1):
            try:
                # Проверяем, не существует ли уже такое место
                existing = db.query(Place).filter(
                    Place.source_url == place_data['source_url']
                ).first()
                
                if existing:
                    logger.info(f"⏭️  Место уже существует: {place_data['name']}")
                    skipped_count += 1
                    continue
                
                # Создаем новое место
                place = Place(
                    name=place_data['name'],
                    description_full=place_data['description_full'],
                    category='fitness_gym',  # Muay Thai gyms
                    tags_csv='',
                    summary='',
                    lat=13.7563,  # Bangkok center
                    lng=100.5018,
                    source='muay_thai_batch_01',
                    source_url=place_data['source_url'],
                    raw_payload=json.dumps({
                        'name': place_data['name'],
                        'description_full': place_data['description_full'],
                        'source_url': place_data['source_url'],
                        'category': 'fitness_gym'
                    }),
                    scraped_at=datetime.now(),
                    processing_status='new'  # Будет обработано GPT воркером
                )
                
                db.add(place)
                db.commit()
                
                logger.info(f"✅ Добавлено место {i}/{len(places_data)}: {place_data['name']}")
                added_count += 1
                
            except Exception as e:
                logger.error(f"❌ Ошибка при добавлении места {place_data['name']}: {e}")
                db.rollback()
                continue
        
        logger.info(f"🎉 Ингестия завершена!")
        logger.info(f"✅ Добавлено: {added_count}")
        logger.info(f"⏭️  Пропущено: {skipped_count}")
        
        return added_count
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Ингестия Muay Thai мест из CSV')
    parser.add_argument('--csv-file', required=True, help='Путь к CSV файлу')
    parser.add_argument('--limit', type=int, help='Максимальное количество мест')
    parser.add_argument('--verbose', '-v', action='store_true', help='Подробное логирование')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        count = ingest_muay_thai_places(args.csv_file, args.limit)
        print(f"\n🎉 Успешно добавлено {count} мест!")
        print("💡 Теперь запустите GPT воркер для обработки:")
        print("   python apps/places/commands/run_gpt_worker.py --batch-size 5")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
