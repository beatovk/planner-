#!/usr/bin/env python3
"""Скрипт для мониторинга прогресса обработки"""

import time
from apps.core.db import SessionLocal
from apps.places.models import Place
from sqlalchemy import func

def check_progress():
    """Проверка прогресса обработки"""
    db = SessionLocal()
    try:
        # Статистика по статусам
        status_stats = db.query(
            Place.processing_status,
            func.count(Place.id).label('count')
        ).group_by(Place.processing_status).all()
        
        print(f'📊 ПРОГРЕСС ОБРАБОТКИ - {time.strftime("%H:%M:%S")}:')
        for status, count in status_stats:
            print(f'  {status}: {count}')
        
        # Процент завершения
        total = sum(count for _, count in status_stats)
        processed = sum(count for status, count in status_stats if status in ['summarized', 'error'])
        if total > 0:
            progress = (processed / total) * 100
            print(f'\n📈 ПРОГРЕСС: {progress:.1f}% ({processed}/{total})')
            
            # Оценка времени
            if processed > 0:
                remaining = total - processed
                estimated_time = (remaining / 20) * 2  # 20 мест в батче, ~2 минуты на батч
                print(f'⏱️ Осталось примерно: {estimated_time:.0f} минут')
        
        return processed, total
        
    finally:
        db.close()

if __name__ == "__main__":
    print("🔄 Мониторинг прогресса обработки...")
    print("Нажмите Ctrl+C для остановки")
    print()
    
    try:
        while True:
            processed, total = check_progress()
            print("-" * 50)
            
            if processed >= total:
                print("✅ Обработка завершена!")
                break
                
            time.sleep(30)  # Проверяем каждые 30 секунд
            
    except KeyboardInterrupt:
        print("\n🛑 Мониторинг остановлен")
