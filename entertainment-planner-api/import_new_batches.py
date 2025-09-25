#!/usr/bin/env python3
"""
Скрипт для импорта мест из трех новых CSV файлов:
- + Bangkokmalls.csv
- +Bangkok_Food___Batch_08__next_100__6__sentences__no_photos_.csv
- +bkk_food_batch_11_100_no_photos_min6_v2.csv
"""

import os
import sys
import csv
import psycopg
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv(Path(__file__).parent / '.env')

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Исправляем URL для psycopg
db_url = os.getenv("DATABASE_URL", "postgresql://ep:ep@localhost:5432/ep")
if "+psycopg" in db_url:
    db_url = db_url.replace("+psycopg", "")
DB_URL = db_url

# Пути к CSV файлам
CSV_FILES = [
    {
        'path': Path("/Users/user/entertainment planner/docs/places.csv/+ Bangkokmalls.csv"),
        'source': 'bangkok_malls',
        'category': 'mall'
    },
    {
        'path': Path("/Users/user/entertainment planner/docs/places.csv/+Bangkok_Food___Batch_08__next_100__6__sentences__no_photos_.csv"),
        'source': 'bangkok_food_batch_08',
        'category': 'restaurant'
    },
    {
        'path': Path("/Users/user/entertainment planner/docs/places.csv/+bkk_food_batch_11_100_no_photos_min6_v2.csv"),
        'source': 'bkk_food_batch_11',
        'category': 'restaurant'
    }
]

def import_csv_batch(csv_file_info):
    """Импортирует места из одного CSV файла."""
    
    csv_path = csv_file_info['path']
    source = csv_file_info['source']
    category = csv_file_info['category']
    
    print(f"📁 Импорт из {csv_path.name}...")
    
    if not csv_path.exists():
        print(f"❌ Файл не найден: {csv_path}")
        return 0, 0
    
    conn = None
    try:
        conn = psycopg.connect(DB_URL)
        cursor = conn.cursor()
        
        imported_count = 0
        skipped_count = 0
        
        with open(csv_path, mode='r', encoding='utf-8-sig') as file:
            # Определяем разделитель по первой строке
            first_line = file.readline()
            file.seek(0)
            
            if ';' in first_line:
                reader = csv.DictReader(file, delimiter=';')
            else:
                reader = csv.DictReader(file, delimiter=',')
            
            for row in reader:
                name = row.get('name', '').strip()
                description_full = row.get('description_full', '').strip()
                
                if not name or not description_full:
                    print(f"⚠️ Пропущено (пустые данные): {name}")
                    skipped_count += 1
                    continue
                
                # Проверяем, существует ли уже место с таким названием
                cursor.execute("SELECT id FROM places WHERE name = %s", (name,))
                if cursor.fetchone():
                    print(f"⚠️ Пропущено (уже существует): {name}")
                    skipped_count += 1
                    continue
                
                # Вставляем новое место
                cursor.execute('''
                INSERT INTO places (
                    name, category, description_full, source, 
                    processing_status, scraped_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s
                )
                ''', (
                    name,
                    category,
                    description_full,
                    source,
                    'new',
                    datetime.now(),
                    datetime.now()
                ))
                
                print(f"✅ Импортировано: {name}")
                imported_count += 1
        
        # Коммитим изменения
        conn.commit()
        
        print(f"📊 Результаты {csv_path.name}:")
        print(f"   ✅ Импортировано: {imported_count} мест")
        print(f"   ⚠️ Пропущено: {skipped_count} мест")
        
        return imported_count, skipped_count
        
    except Exception as e:
        print(f"❌ Ошибка импорта {csv_path.name}: {e}")
        if conn:
            conn.rollback()
        return 0, 0
    finally:
        if conn:
            conn.close()

def import_all_batches():
    """Импортирует все CSV файлы."""
    
    print("🚀 ИМПОРТ НОВЫХ ПАРТИЙ МЕСТ")
    print("=" * 50)
    
    total_imported = 0
    total_skipped = 0
    
    for csv_file_info in CSV_FILES:
        imported, skipped = import_csv_batch(csv_file_info)
        total_imported += imported
        total_skipped += skipped
        print()
    
    print("🎉 ИТОГОВЫЕ РЕЗУЛЬТАТЫ:")
    print(f"✅ Всего импортировано: {total_imported} мест")
    print(f"⚠️ Всего пропущено: {total_skipped} мест")
    
    # Статистика по источникам
    conn = None
    try:
        conn = psycopg.connect(DB_URL)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT source, COUNT(*) FROM places
            WHERE source IN ('bangkok_malls', 'bangkok_food_batch_08', 'bkk_food_batch_11')
            GROUP BY source ORDER BY COUNT(*) DESC
        ''')
        source_stats = cursor.fetchall()
        
        print(f"\n📂 СТАТИСТИКА ПО ИСТОЧНИКАМ:")
        for source, count in source_stats:
            print(f"   {source}: {count} мест")
            
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    import_all_batches()
