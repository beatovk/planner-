#!/usr/bin/env python3
"""
Load real data from source database to staging
"""
import os
import pandas as pd
from sqlalchemy import create_engine, text

# Исходная база данных
SOURCE_URL = "postgresql+psycopg://postgres:1234@localhost:5432/ep"
# Staging база данных
STAGING_URL = os.getenv('DATABASE_URL')

def load_real_data():
    if not STAGING_URL:
        print("❌ STAGING_URL not set")
        return 1
    
    print("🔄 Connecting to source database...")
    source_engine = create_engine(SOURCE_URL)
    
    print("🔄 Connecting to staging database...")
    staging_engine = create_engine(STAGING_URL)
    
    try:
        # Проверяем подключение к исходной базе
        with source_engine.connect() as conn:
            source_count = conn.execute(text("SELECT COUNT(*) FROM places")).scalar()
            print(f"📊 Source places count: {source_count}")
        
        # Читаем данные из исходной базы
        print("📥 Reading data from source...")
        df = pd.read_sql_table("places", source_engine)
        print(f"📊 Read {len(df)} rows from source")
        
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
    exit(load_real_data())
