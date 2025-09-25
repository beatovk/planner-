#!/usr/bin/env python3
"""
Скрипт для добавления мест из +bkk_food_batch_11_100_no_photos_min6_v2.csv
"""

import os
import sys
import csv
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.core.db import SessionLocal
from apps.places.models import Place

def add_places_from_csv():
    """Добавляет места из CSV файла в базу данных"""
    
    # Путь к CSV файлу
    csv_file_path = "../docs/places.csv/+bkk_food_batch_11_100_no_photos_min6_v2.csv"
    
    if not os.path.exists(csv_file_path):
        print(f"❌ Файл не найден: {csv_file_path}")
        return
    
    db = SessionLocal()
    added_count = 0
    skipped_count = 0
    
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                name = row.get('name', '').strip()
                description = row.get('description_full', '').strip()
                
                if not name or not description:
                    print(f"⚠️ Пропускаем строку с пустыми данными: {row}")
                    continue
                
                # Проверяем, существует ли уже место с таким названием
                existing_place = db.query(Place).filter(
                    Place.name == name
                ).first()
                
                if existing_place:
                    print(f"⏭️ Место уже существует: {name}")
                    skipped_count += 1
                    continue
                
                # Создаем новое место
                new_place = Place(
                    name=name,
                    description_full=description,
                    category="restaurant",
                    processing_status="new",
                    source="bkk_food_batch_11",
                    source_url=f"bkk_food_batch_11_{name.lower().replace(' ', '_').replace('(', '').replace(')', '').replace(',', '')}",
                    scraped_at=datetime.now()
                )
                
                db.add(new_place)
                added_count += 1
                print(f"✅ Добавлено: {name}")
            
            db.commit()
            print(f"\n📊 Результат:")
            print(f"  Добавлено новых мест: {added_count}")
            print(f"  Пропущено (уже существуют): {skipped_count}")
            print(f"  Всего обработано: {added_count + skipped_count}")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Добавление мест из +bkk_food_batch_11_100_no_photos_min6_v2.csv")
    print("=" * 70)
    add_places_from_csv()
