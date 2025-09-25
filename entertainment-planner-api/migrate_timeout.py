#!/usr/bin/env python3
import signal
import sys
from sqlalchemy import create_engine, text

def timeout_handler(signum, frame):
    raise TimeoutError("Операция превысила время ожидания")

def main():
    # Устанавливаем таймаут 30 секунд
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(30)
    
    try:
        engine = create_engine('postgresql+psycopg://postgres:1234@localhost:5432/ep', pool_timeout=10)
        
        print("Подключаемся к базе...")
        with engine.begin() as conn:
            print("✅ Подключение установлено")
            
            print("Добавляем поле signals...")
            conn.execute(text("ALTER TABLE places ADD COLUMN IF NOT EXISTS signals jsonb DEFAULT '{}'::jsonb"))
            print("✅ Поле signals добавлено")
            
            print("Переносим данные...")
            result = conn.execute(text("UPDATE places SET signals = interest_signals WHERE interest_signals IS NOT NULL"))
            print(f"✅ Обновлено {result.rowcount} записей")
            
            print("Обновляем MV...")
            conn.execute(text("REFRESH MATERIALIZED VIEW epx.places_search_mv"))
            print("✅ MV обновлен")
            
        print("🎉 Миграция завершена!")
        
    except TimeoutError:
        print("❌ Операция превысила время ожидания")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)
    finally:
        signal.alarm(0)

if __name__ == "__main__":
    main()
