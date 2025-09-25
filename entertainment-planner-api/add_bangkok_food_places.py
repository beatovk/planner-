#!/usr/bin/env python3
"""
Скрипт для добавления мест из Bangkok Food CSV файла в базу данных
"""

import csv
import sys
import os
from datetime import datetime
from typing import List, Dict, Any

# Добавляем путь к приложению
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.core.db import SessionLocal
from apps.places.models import Place

def add_places_from_csv(csv_file_path: str) -> None:
    """Добавляет места из CSV файла в базу данных"""
    
    db = SessionLocal()
    added_count = 0
    skipped_count = 0
    duplicate_count = 0
    
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                name = row.get('name', '').strip()
                description = row.get('description_full', '').strip()
                
                if not name or not description:
                    print(f"⚠️  Пропущено: пустое название или описание")
                    skipped_count += 1
                    continue
                
                # Проверяем, существует ли уже место с таким названием
                existing_place = db.query(Place).filter(Place.name == name).first()
                if existing_place:
                    print(f"⚠️  Дубликат: место '{name}' уже существует (ID: {existing_place.id})")
                    duplicate_count += 1
                    continue
                
                # Создаем новое место
                new_place = Place(
                    name=name,
                    description_full=description,
                    category="restaurant",  # По умолчанию ресторан
                    processing_status="new",
                    source="bangkok_food_csv",
                    source_url=f"bangkok_food_csv_{name.lower().replace(' ', '_')}",  # Уникальный URL
                    scraped_at=datetime.now()
                )
                
                db.add(new_place)
                db.commit()
                
                print(f"✅ Добавлено: '{name}' (ID: {new_place.id})")
                added_count += 1
                
    except Exception as e:
        print(f"❌ Ошибка при обработке CSV: {e}")
        db.rollback()
        raise
    finally:
        db.close()
    
    print(f"\n📊 Итого:")
    print(f"   Добавлено: {added_count}")
    print(f"   Дубликатов: {duplicate_count}")
    print(f"   Пропущено: {skipped_count}")

def main():
    """Основная функция"""
    csv_file_path = "../docs/places.csv/Bangkok_Food___Batch_06__100_restaurants__min_6_sentences__no_photos_.csv"
    
    if not os.path.exists(csv_file_path):
        print(f"❌ Файл не найден: {csv_file_path}")
        return
    
    print(f"🔄 Добавление мест из {csv_file_path}...")
    add_places_from_csv(csv_file_path)

if __name__ == "__main__":
    main()
