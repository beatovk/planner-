#!/usr/bin/env python3
import sys
from sqlalchemy import create_engine, text

def main():
    try:
        engine = create_engine('postgresql+psycopg://postgres:1234@localhost:5432/ep')
        
        with engine.begin() as conn:  # begin() автоматически коммитит
            print("1. Добавляем поле signals...")
            conn.execute(text("ALTER TABLE places ADD COLUMN IF NOT EXISTS signals jsonb DEFAULT '{}'::jsonb"))
            
            print("2. Переносим данные...")
            result = conn.execute(text("UPDATE places SET signals = interest_signals WHERE interest_signals IS NOT NULL"))
            print(f"   Обновлено {result.rowcount} записей")
            
            print("3. Создаем схему...")
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS epx AUTHORIZATION postgres"))
            
            print("4. Создаем MV...")
            conn.execute(text("""
                DROP MATERIALIZED VIEW IF EXISTS epx.places_search_mv;
                CREATE MATERIALIZED VIEW epx.places_search_mv AS
                SELECT p.id, p.name, p.category, p.summary, p.tags_csv, p.lat, p.lng,
                       p.picture_url, p.gmaps_place_id, p.gmaps_url, p.rating, p.processing_status,
                       to_tsvector('simple', coalesce(p.name,'') || ' ' || coalesce(p.category,'') || ' ' || coalesce(p.tags_csv,'') || ' ' || coalesce(p.summary,'')) AS search_vector,
                       COALESCE(p.signals, '{}'::jsonb) AS signals
                FROM public.places p
            """))
            
            print("5. Создаем индексы...")
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS places_search_mv_pk ON epx.places_search_mv (id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS places_search_mv_gin ON epx.places_search_mv USING gin (search_vector)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS places_search_mv_signals_gin ON epx.places_search_mv USING gin (signals)"))
            
            print("6. Обновляем MV...")
            conn.execute(text("REFRESH MATERIALIZED VIEW epx.places_search_mv"))
            
        print("✅ Миграция завершена!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()