#!/usr/bin/env python3
"""
Скрипт для мониторинга прогресса обработки новых партий мест.
"""

import time
import os
import sys
import psycopg
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv(Path(__file__).parent / '.env')

# Добавляем путь к проекту
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Исправляем URL для psycopg
db_url = os.getenv("DATABASE_URL", "postgresql://ep:ep@localhost:5432/ep")
if "+psycopg" in db_url:
    db_url = db_url.replace("+psycopg", "")
DB_URL = db_url

def get_processing_progress():
    """Получает текущий прогресс обработки новых мест из БД."""
    conn = None
    try:
        conn = psycopg.connect(DB_URL)
        cursor = conn.cursor()

        # Общая статистика по новым партиям
        cursor.execute('''
            SELECT 
                source,
                COUNT(*) as total_places,
                COUNT(CASE WHEN processing_status = 'summarized' THEN 1 END) as summarized,
                COUNT(CASE WHEN processing_status = 'new' THEN 1 END) as new,
                COUNT(CASE WHEN processing_status = 'error' THEN 1 END) as error
            FROM places
            WHERE source IN ('bangkok_malls', 'bangkok_food_batch_08', 'bkk_food_batch_11')
            GROUP BY source
            ORDER BY source
        ''')
        source_stats = cursor.fetchall()

        # Последние 5 обработанных мест
        cursor.execute('''
            SELECT name, summary, source, updated_at
            FROM places
            WHERE source IN ('bangkok_malls', 'bangkok_food_batch_08', 'bkk_food_batch_11')
            AND processing_status = 'summarized'
            ORDER BY updated_at DESC
            LIMIT 5
        ''')
        last_processed = cursor.fetchall()

        return source_stats, last_processed
    except Exception as e:
        print(f"❌ Ошибка при получении прогресса: {e}")
        return [], []
    finally:
        if conn:
            conn.close()

def display_progress():
    """Отображает прогресс в терминале."""
    while True:
        os.system('clear') # Очищаем терминал
        print("🚀 МОНИТОРИНГ ПРОГРЕССА ОБРАБОТКИ НОВЫХ ПАРТИЙ")
        print("=" * 60)

        source_stats, last_processed = get_processing_progress()

        if not source_stats:
            print("Нет данных для мониторинга.")
            print(f"\nОбновление каждые 5 секунд... (Ctrl+C для выхода)")
            time.sleep(5)
            continue

        total_places = sum(count for _, count, _, _, _ in source_stats)
        total_summarized = sum(summarized for _, _, summarized, _, _ in source_stats)
        total_new = sum(new for _, _, _, new, _ in source_stats)
        total_error = sum(error for _, _, _, _, error in source_stats)

        print(f"📊 ОБЩАЯ СТАТИСТИКА:")
        print(f"   Всего мест: {total_places}")
        print(f"   ✅ Обработано: {total_summarized}/{total_places} ({total_summarized/total_places*100:.1f}%)")
        print(f"   🔄 В ожидании: {total_new}/{total_places} ({total_new/total_places*100:.1f}%)")
        print(f"   ❌ С ошибками: {total_error}/{total_places} ({total_error/total_places*100:.1f}%)")

        print(f"\n📂 СТАТИСТИКА ПО ПАРТИЯМ:")
        for source, total, summarized, new, error in source_stats:
            print(f"   {source}:")
            print(f"     Всего: {total} | ✅ {summarized} | 🔄 {new} | ❌ {error}")

        if last_processed:
            print(f"\n🎯 ПОСЛЕДНИЕ ОБРАБОТАННЫЕ МЕСТА:")
            for name, summary, source, updated_at in last_processed:
                print(f"  - {name} ({source})")
                print(f"    📝 {summary[:70]}..." if summary else "    📝 Нет саммари")
                print(f"    ⏰ {updated_at.strftime('%H:%M:%S')}")
                print()
        else:
            print("\nНет недавно обработанных мест.")

        print(f"\nОбновление каждые 5 секунд... (Ctrl+C для выхода)")
        time.sleep(5)

if __name__ == "__main__":
    display_progress()
