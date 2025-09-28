#!/usr/bin/env python3
"""
Load filtered CSV data to staging
"""
import os
import pandas as pd
from sqlalchemy import create_engine, text

# Staging база данных
STAGING_URL = os.getenv('DATABASE_URL')

def load_filtered_csv():
    if not STAGING_URL:
        print("❌ STAGING_URL not set")
        return 1
    
    print("🔄 Connecting to staging database...")
    staging_engine = create_engine(STAGING_URL)
    
    try:
        # Читаем CSV
        print("📥 Reading CSV data...")
        df = pd.read_csv('places_filtered.csv')
        print(f"📊 Read {len(df)} rows from CSV")
        
        # Очищаем staging таблицу
        print("🧹 Clearing staging table...")
        with staging_engine.begin() as conn:
            conn.execute(text("DELETE FROM public.places"))
            print("✅ Staging table cleared")
        
        # Загружаем данные в staging
        print("📤 Loading data to staging...")
        df.to_sql("places", staging_engine, if_exists="append", index=False)
        print(f"✅ Loaded {len(df)} rows to staging")
        
        # Обновляем материализованное представление
        print("🔄 Refreshing materialized view...")
        with staging_engine.begin() as conn:
            conn.execute(text("REFRESH MATERIALIZED VIEW epx.places_search_mv"))
            print("✅ Materialized view refreshed")
        
        # Проверяем результат
        print("🔍 Checking final counts...")
        with staging_engine.begin() as conn:
            places_count = conn.execute(text("SELECT COUNT(*) FROM public.places")).scalar()
            mv_count = conn.execute(text("SELECT COUNT(*) FROM epx.places_search_mv")).scalar()
            
            flags = conn.execute(text("""
                SELECT 
                    SUM(is_chill::int) as chill,
                    SUM(is_romantic::int) as romantic,
                    SUM(is_cinema::int) as cinema
                FROM epx.places_search_mv
            """)).fetchone()
            
            print(f"📊 Final counts:")
            print(f"  - Places: {places_count}")
            print(f"  - MV: {mv_count}")
            print(f"  - Derived flags: chill={flags[0]}, romantic={flags[1]}, cinema={flags[2]}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    exit(load_filtered_csv())
