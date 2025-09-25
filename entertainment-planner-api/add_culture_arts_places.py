#!/usr/bin/env python3
"""
Добавление мест культуры и искусства из CSV файла
"""

import csv
import os
import sys
from datetime import datetime
from sqlalchemy.exc import IntegrityError

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.core.db import SessionLocal
from apps.places.models import Place

def add_culture_arts_places(file_path: str):
    """Добавить места культуры и искусства из CSV"""
    db = SessionLocal()
    added_count = 0
    skipped_count = 0
    total_rows = 0

    try:
        with open(file_path, mode='r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            places_to_add = []
            
            for row in reader:
                total_rows += 1
                name = row.get('name')
                subcategory = row.get('subcategory')
                description_full = row.get('description_full')
                source_url = row.get('source_url')

                if not name or not description_full:
                    print(f"⚠️ Пропущено место из-за отсутствия имени или описания: {row}")
                    skipped_count += 1
                    continue

                # Генерируем уникальный source_url если не указан
                if not source_url:
                    source_url = f"culture_arts_batch_02_{name.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('—', '_').replace('.', '').replace(',', '')}"

                # Проверяем дубликаты
                existing_place = db.query(Place).filter(
                    (Place.name == name) | (Place.source_url == source_url)
                ).first()

                if existing_place:
                    skipped_count += 1
                    continue

                # Определяем категорию на основе subcategory
                category = "gallery"
                if subcategory == "Museum":
                    category = "museum"
                elif subcategory == "Theatre & Show":
                    category = "theater"
                elif subcategory == "Cinema":
                    category = "cinema"

                new_place = Place(
                    name=name,
                    description_full=description_full,
                    category=category,
                    processing_status="new",
                    source="culture_arts_batch_02",
                    source_url=source_url,
                    scraped_at=datetime.now()
                )
                places_to_add.append(new_place)

            if places_to_add:
                db.bulk_save_objects(places_to_add)
                db.commit()
                added_count = len(places_to_add)
                print(f"✅ Добавлено {added_count} новых мест культуры и искусства")

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
    csv_file_path = '../docs/places.csv/+ Bangkok_Culture___Arts___Batch_02__verified_.csv'
    print(f"🚀 Добавление мест культуры и искусства из {csv_file_path.split('/')[-1]}\n" + "="*60)
    add_culture_arts_places(csv_file_path)
