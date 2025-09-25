#!/usr/bin/env python3
"""
Скрипт для добавления новых мест из CSV файлов в базу данных
"""

import os
import sys
import csv
import psycopg
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv(Path(__file__).parent / '.env')

# Исправляем URL для psycopg
db_url = os.getenv("DATABASE_URL", "postgresql://ep:ep@localhost:5432/ep")
if "+psycopg" in db_url:
    db_url = db_url.replace("+psycopg", "")
DB_URL = db_url

def add_places_from_csv(csv_file_path, source_name, category="entertainment"):
    """Добавляет места из CSV файла в базу данных"""
    
    conn = psycopg.connect(DB_URL)
    cursor = conn.cursor()
    
    added_count = 0
    skipped_count = 0
    
    print(f"📁 Обрабатываем файл: {csv_file_path}")
    print(f"📊 Источник: {source_name}")
    print(f"🏷️ Категория: {category}")
    print("-" * 60)
    
    with open(csv_file_path, 'r', encoding='utf-8') as file:
        # Определяем разделитель
        sample = file.read(1024)
        file.seek(0)
        
        if '\t' in sample:
            delimiter = '\t'
        else:
            delimiter = ','
        
        reader = csv.DictReader(file, delimiter=delimiter)
        
        for row in reader:
            # Нормализуем ключи заголовков к нижнему регистру для совместимости с "Name","Description"
            # и убираем пробелы по краям
            row = { (k or '').strip().lower(): (v or '') for k, v in row.items() }
            # Извлекаем данные в зависимости от структуры CSV
            name = (row.get('name') or '').strip()
            description = (row.get('description_full') or row.get('description') or '').strip()
            subcategory = (row.get('subcategory') or '').strip()
            source_url = (row.get('source_url') or '').strip()
            
            if not name:
                print(f"⚠️ Пропускаем строку без названия: {row}")
                skipped_count += 1
                continue
            
            # Проверяем, существует ли уже такое место по названию и источнику
            cursor.execute('''
                SELECT id FROM places 
                WHERE name = %s AND source = %s
            ''', (name, source_name))
            
            if cursor.fetchone():
                print(f"⏭️ Место уже существует: {name}")
                skipped_count += 1
                continue
            
            # Проверяем, существует ли уже такое место по source_url (только если URL не пустой)
            if source_url and source_url.strip():
                cursor.execute('''
                    SELECT id FROM places 
                    WHERE source_url = %s
                ''', (source_url,))
                
                if cursor.fetchone():
                    print(f"⏭️ URL уже существует: {source_url}")
                    skipped_count += 1
                    continue
            
            # Добавляем место в базу данных
            try:
                cursor.execute('''
                    INSERT INTO places (
                        name, 
                        description_full, 
                        category,
                        source, 
                        source_url, 
                        processing_status,
                        scraped_at,
                        updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    name,
                    description,
                    category,
                    source_name,
                    source_url if source_url and source_url.strip() else None,
                    'new',
                    datetime.now(timezone.utc),
                    datetime.now(timezone.utc)
                ))
                
                print(f"✅ Добавлено: {name}")
                added_count += 1
                
            except Exception as e:
                print(f"❌ Ошибка при добавлении {name}: {e}")
                skipped_count += 1
    
    conn.commit()
    conn.close()
    
    print(f"\n📊 Результат обработки {csv_file_path}:")
    print(f"  ✅ Добавлено: {added_count}")
    print(f"  ⏭️ Пропущено: {skipped_count}")
    print()
    
    return added_count, skipped_count

def main():
    """Главная функция"""
    print("🚀 ДОБАВЛЕНИЕ НОВЫХ МЕСТ ИЗ CSV ФАЙЛОВ")
    print("=" * 60)
    
    # Список файлов для обработки
    csv_files = [
        {
            'path': '../docs/places.csv/+Nightlife___Batch_02__verified__no_photos__24_venues_.csv',
            'source': 'Nightlife Batch 02',
            'category': 'nightlife'
        },
        {
            'path': '../docs/places.csv/+Top_Clubs__Batch_01_.csv',
            'source': 'Top Clubs Batch 01',
            'category': 'nightlife'
        },
        {
            'path': '../docs/places.csv/1_entertainment_places.csv',
            'source': 'Entertainment Places',
            'category': 'entertainment'
        },
        {
            'path': '../docs/places.csv/1.csv',
            'source': 'Restaurants Batch 01',
            'category': 'restaurant'
        }
    ]
    
    total_added = 0
    total_skipped = 0
    
    for csv_file in csv_files:
        if os.path.exists(csv_file['path']):
            added, skipped = add_places_from_csv(
                csv_file['path'], 
                csv_file['source'], 
                csv_file['category']
            )
            total_added += added
            total_skipped += skipped
        else:
            print(f"❌ Файл не найден: {csv_file['path']}")
    
    print("🎯 ИТОГОВАЯ СТАТИСТИКА:")
    print(f"  ✅ Всего добавлено: {total_added}")
    print(f"  ⏭️ Всего пропущено: {total_skipped}")
    
    # Проверяем общее количество мест в базе
    conn = psycopg.connect(DB_URL)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM places')
    total_places = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM places WHERE processing_status = 'new'")
    new_places = cursor.fetchone()[0]
    
    print(f"\n📊 СТАТИСТИКА БАЗЫ ДАННЫХ:")
    print(f"  📍 Всего мест: {total_places}")
    print(f"  🆕 Новых мест: {new_places}")
    
    conn.close()

if __name__ == "__main__":
    main()
