#!/usr/bin/env python3
"""
Скрипт для импорта мест из CSV файла Culture & Arts Batch 02
"""

import os
import sys
import csv
import psycopg
from pathlib import Path
from datetime import datetime

def import_culture_arts():
    """Импорт мест из CSV файла в базу данных"""
    
    print("🎨 Импорт мест Culture & Arts Batch 02...")
    
    # Путь к CSV файлу
    csv_path = Path(__file__).parent.parent / "docs" / "places.csv" / "+ Bangkok_Culture___Arts___Batch_02__verified_.csv"
    
    if not csv_path.exists():
        print(f"❌ Файл не найден: {csv_path}")
        return
    
    # Подключаемся к БД
    conn = psycopg.connect('postgresql://ep:ep@localhost:5432/ep')
    cursor = conn.cursor()
    
    try:
        imported_count = 0
        skipped_count = 0
        
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                name = row['name'].strip()
                subcategory = row['subcategory'].strip()
                description_full = row['description_full'].strip()
                source_url = row['source_url'].strip()
                
                if not name or not description_full:
                    print(f"⚠️ Пропущено: {name} - нет названия или описания")
                    skipped_count += 1
                    continue
                
                # Проверяем, есть ли уже такое место
                cursor.execute('''
                SELECT id FROM places 
                WHERE name = %s OR source_url = %s
                ''', (name, source_url))
                
                if cursor.fetchone():
                    print(f"⚠️ Уже существует: {name}")
                    skipped_count += 1
                    continue
                
                # Определяем категорию на основе subcategory
                category = "culture_arts"
                if "Gallery" in subcategory or "Art Space" in subcategory:
                    category = "gallery"
                elif "Museum" in subcategory:
                    category = "museum"
                elif "Theatre" in subcategory or "Show" in subcategory:
                    category = "theater"
                elif "Cinema" in subcategory:
                    category = "cinema"
                
                # Вставляем новое место
                cursor.execute('''
                INSERT INTO places (
                    name, category, description_full, source_url,
                    source, processing_status, scraped_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                ''', (
                    name,
                    category,
                    description_full,
                    source_url,
                    'timeout_bangkok',
                    'new',
                    datetime.now(),
                    datetime.now()
                ))
                
                print(f"✅ Импортировано: {name} ({category})")
                imported_count += 1
        
        # Коммитим изменения
        conn.commit()
        
        print(f"\\n📊 РЕЗУЛЬТАТЫ ИМПОРТА:")
        print(f"✅ Импортировано: {imported_count} мест")
        print(f"⚠️ Пропущено: {skipped_count} мест")
        
        # Показываем статистику по категориям
        cursor.execute('''
        SELECT category, COUNT(*) 
        FROM places 
        WHERE source = 'timeout_bangkok' 
        AND processing_status = 'new'
        GROUP BY category 
        ORDER BY COUNT(*) DESC
        ''')
        category_stats = cursor.fetchall()
        
        print(f"\\n📂 СТАТИСТИКА ПО КАТЕГОРИЯМ:")
        for category, count in category_stats:
            print(f"   {category}: {count} мест")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка импорта: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    import_culture_arts()
