#!/usr/bin/env python3
"""
Простой скрипт для отслеживания прогресса GPT воркера
"""

import psycopg
import time
import os

def watch_progress():
    """Отслеживание прогресса обработки"""
    
    print("🔍 Отслеживание прогресса GPT воркера...")
    print("Нажмите Ctrl+C для выхода")
    print("=" * 50)
    
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
            SELECT name, updated_at, summary
            FROM places 
            WHERE description_full IS NOT NULL 
            AND description_full != '' 
            AND description_full != 'N/A'
            AND processing_status = 'summarized'
            ORDER BY updated_at DESC 
            LIMIT 3
            ''')
            recent = cursor.fetchall()
            
            conn.close()
            
            # Очищаем экран
            os.system('clear' if os.name == 'posix' else 'cls')
            
            print(f"🕐 {time.strftime('%H:%M:%S')} - Прогресс обработки")
            print("=" * 50)
            
            # Общая статистика
            total = 0
            for status, count in stats:
                status_emoji = {
                    'new': '⏳',
                    'summarized': '✅', 
                    'enriched': '🔍',
                    'published': '🚀',
                    'error': '❌'
                }.get(status, '❓')
                print(f"{status_emoji} {status}: {count}")
                total += count
            
            # Прогресс-бар
            processed = sum(count for status, count in stats if status == 'summarized')
            progress = (processed / total * 100) if total > 0 else 0
            bar_length = 30
            filled_length = int(bar_length * progress / 100)
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            print(f"\n📊 Прогресс: [{bar}] {progress:.1f}% ({processed}/{total})")
            
            # Последние обработанные места
            if recent:
                print(f"\n🎯 Последние обработанные места:")
                for i, (name, updated_at, summary) in enumerate(recent, 1):
                    summary_short = summary[:60] + "..." if summary and len(summary) > 60 else summary or "Нет саммари"
                    print(f"  {i}. {name}")
                    print(f"     📝 {summary_short}")
                    print(f"     ⏰ {updated_at.strftime('%H:%M:%S')}")
                    print()
            
            print("=" * 50)
            print("Обновление каждые 3 секунды... (Ctrl+C для выхода)")
            
            time.sleep(3)
            
    except KeyboardInterrupt:
        print("\n\n👋 Отслеживание остановлено")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")

if __name__ == "__main__":
    watch_progress()
