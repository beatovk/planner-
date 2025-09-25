#!/usr/bin/env python3
"""
Добавление музыкальных баров из CSV файла
"""

import csv
import os
import sys
from datetime import datetime
from sqlalchemy.exc import IntegrityError

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.core.db import SessionLocal
from apps.places.models import Place

def add_music_bars(file_path: str):
    """Добавить музыкальные бары из CSV"""
    db = SessionLocal()
    added_count = 0
    skipped_count = 0
    total_rows = 0
    used_urls = set()

    try:
        with open(file_path, mode='r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            places_to_add = []
            
            for row in reader:
                total_rows += 1
                name = row.get('name')
                description_full = row.get('description_full')

                if not name or not description_full:
                    print(f"⚠️ Пропущено место из-за отсутствия имени или описания: {row}")
                    skipped_count += 1
                    continue

                # Генерируем уникальный source_url
                base_url = f"music_bars_40_{name.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('—', '_').replace('.', '').replace(',', '').replace('&', 'and').replace(':', '').replace('!', '').replace('?', '')}"
                
                # Проверяем уникальность URL
                counter = 1
                source_url = base_url
                while source_url in used_urls:
                    source_url = f"{base_url}_{counter}"
                    counter += 1
                
                used_urls.add(source_url)

                # Проверяем дубликаты
                existing_place = db.query(Place).filter(
                    (Place.name == name) | (Place.source_url == source_url)
                ).first()

                if existing_place:
                    skipped_count += 1
                    continue

                new_place = Place(
                    name=name,
                    description_full=description_full,
                    category="bar",
                    processing_status="new",
                    source="music_bars_40",
                    source_url=source_url,
                    scraped_at=datetime.now()
                )
                places_to_add.append(new_place)

            if places_to_add:
                db.bulk_save_objects(places_to_add)
                db.commit()
                added_count = len(places_to_add)

    except IntegrityError as e:
        db.rollback()
        print(f"❌ Ошибка целостности базы данных: {e}")
    except Exception as e:
        db.rollback()
        print(f"❌ Произошла ошибка: {e}")
    finally:
        db.close()

    print(f"\n📊 Результат:")
    print(f"  Добавлено новых мест: {added_count}")
    print(f"  Пропущено (уже существуют): {skipped_count}")
    print(f"  Всего обработано: {total_rows}")

if __name__ == "__main__":
    csv_file_path = '../docs/places.csv/music_bars_40.csv'
    print(f"🚀 Добавление музыкальных баров из {csv_file_path.split('/')[-1]}\n" + "="*60)
    add_music_bars(csv_file_path)
