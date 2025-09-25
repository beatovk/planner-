#!/usr/bin/env python3
"""
Скрипт для мониторинга прогресса GPT воркера в реальном времени.
Показывает какое место обрабатывается и общую статистику.
"""

import psycopg
import time
import os
from datetime import datetime

def monitor_gpt_worker():
    """Мониторинг прогресса GPT воркера"""
    
    print("🔍 Мониторинг GPT воркера...")
    print("Нажмите Ctrl+C для выхода")
    print("=" * 60)
    
    try:
        while True:
            # Подключаемся к БД
            conn = psycopg.connect('postgresql://ep:ep@localhost:5432/ep')
            cursor = conn.cursor()
            
            # Получаем статистику
            cursor.execute('''
            SELECT processing_status, COUNT(*) 
            FROM places 
            WHERE description_full IS NOT NULL 
            AND description_full != '' 
            AND description_full != 'N/A'
            GROUP BY processing_status 
            ORDER BY processing_status
            ''')
            stats = cursor.fetchall()
            
            # Получаем последние обработанные места
            cursor.execute('''
            SELECT name, processing_status, updated_at, summary
            FROM places 
            WHERE description_full IS NOT NULL 
            AND description_full != '' 
            AND description_full != 'N/A'
            AND processing_status = 'summarized'
            ORDER BY updated_at DESC 
            LIMIT 3
            ''')
            recent = cursor.fetchall()
            
            # Получаем текущее место в обработке (если есть)
            cursor.execute('''
            SELECT name, processing_status, updated_at
            FROM places 
            WHERE description_full IS NOT NULL 
            AND description_full != '' 
            AND description_full != 'N/A'
            AND processing_status = 'new'
            ORDER BY updated_at ASC 
            LIMIT 1
            ''')
            current = cursor.fetchone()
            
            conn.close()
            
            # Очищаем экран и выводим информацию
            os.system('clear' if os.name == 'posix' else 'cls')
            
            print(f"🕐 {datetime.now().strftime('%H:%M:%S')} - Мониторинг GPT воркера")
            print("=" * 60)
            
            # Общая статистика
            print("📊 Общая статистика:")
            total = 0
            for status, count in stats:
                status_emoji = {
                    'new': '⏳',
                    'summarized': '✅', 
                    'enriched': '🔍',
                    'published': '🚀',
                    'error': '❌'
                }.get(status, '❓')
                print(f"  {status_emoji} {status}: {count}")
                total += count
            
            print(f"📈 Всего мест: {total}")
            
            # Текущее место в обработке
            if current:
                print(f"\n🔄 Сейчас обрабатывается: {current[0]}")
                print(f"   Статус: {current[1]}")
                print(f"   Обновлено: {current[2]}")
            else:
                print("\n✅ Все места обработаны!")
            
            # Последние обработанные места
            if recent:
                print(f"\n🎯 Последние обработанные места:")
                for i, (name, status, updated_at, summary) in enumerate(recent, 1):
                    summary_short = summary[:50] + "..." if summary and len(summary) > 50 else summary or "Нет саммари"
                    print(f"  {i}. {name}")
                    print(f"     📝 {summary_short}")
                    print(f"     ⏰ {updated_at}")
                    print()
            
            print("=" * 60)
            print("Обновление каждые 5 секунд... (Ctrl+C для выхода)")
            
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n\n👋 Мониторинг остановлен")
    except Exception as e:
        print(f"\n❌ Ошибка мониторинга: {e}")

if __name__ == "__main__":
    monitor_gpt_worker()
