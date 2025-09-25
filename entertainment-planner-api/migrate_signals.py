#!/usr/bin/env python3
"""Миграция signals из interest_signals в places.signals"""

from sqlalchemy import create_engine, text

def main():
    engine = create_engine('postgresql+psycopg://postgres:1234@localhost:5432/ep')
    
    with engine.connect() as conn:
        # Добавляем поле signals
        print("Добавляем поле signals...")
        conn.execute(text("ALTER TABLE places ADD COLUMN IF NOT EXISTS signals jsonb DEFAULT '{}'::jsonb"))
        conn.commit()
        print("✅ Поле signals добавлено")
        
        # Переносим данные из interest_signals в signals
        print("Переносим данные из interest_signals в signals...")
        result = conn.execute(text("UPDATE places SET signals = interest_signals WHERE interest_signals IS NOT NULL"))
        conn.commit()
        print(f"✅ Обновлено {result.rowcount} записей")
        
        # Создаем материализованное представление
        print("Создаем материализованное представление...")
        conn.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS epx.places_search_mv AS
            SELECT
              p.id, p.name, p.category, p.summary, p.tags_csv, p.lat, p.lng,
              p.picture_url, p.gmaps_place_id, p.gmaps_url, p.rating, p.processing_status,
              to_tsvector('simple', coalesce(p.name,'') || ' ' || coalesce(p.category,'') || ' ' || coalesce(p.tags_csv,'') || ' ' || coalesce(p.summary,'')) AS search_vector,
              COALESCE(p.signals, '{}'::jsonb) AS signals
            FROM public.places p
        """))
        conn.commit()
        print("✅ Материализованное представление создано")
        
        # Создаем индексы
        print("Создаем индексы...")
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS places_search_mv_pk ON epx.places_search_mv (id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS places_search_mv_gin ON epx.places_search_mv USING gin (search_vector)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS places_search_mv_signals_gin ON epx.places_search_mv USING gin (signals)"))
        conn.commit()
        print("✅ Индексы созданы")
        
        # Обновляем MV
        print("Обновляем материализованное представление...")
        conn.execute(text("REFRESH MATERIALIZED VIEW epx.places_search_mv"))
        conn.commit()
        print("✅ Материализованное представление обновлено")
        
        print("\n🎉 Миграция завершена успешно!")

if __name__ == "__main__":
    main()
