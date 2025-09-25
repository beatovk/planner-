#!/usr/bin/env python3
from sqlalchemy import create_engine, text

def main():
    engine = create_engine('postgresql+psycopg://postgres:1234@localhost:5432/ep', pool_timeout=10)
    
    with engine.begin() as conn:
        print('Добавляем поле signals...')
        conn.execute(text("ALTER TABLE places ADD COLUMN signals jsonb DEFAULT '{}'::jsonb"))
        print('✅ Поле signals добавлено')
        
        print('Переносим данные...')
        result = conn.execute(text("UPDATE places SET signals = interest_signals WHERE interest_signals IS NOT NULL"))
        print(f'✅ Обновлено {result.rowcount} записей')
        
        print('Обновляем MV...')
        conn.execute(text("REFRESH MATERIALIZED VIEW epx.places_search_mv"))
        print('✅ MV обновлен')

if __name__ == "__main__":
    main()
