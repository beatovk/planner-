#!/usr/bin/env python3
"""
Full data migration from source to staging with complete schema
"""
import os
import pandas as pd
from sqlalchemy import create_engine, text

# Исходная база данных
SOURCE_URL = "postgresql+psycopg://postgres:1234@localhost:5432/ep"
# Staging база данных
STAGING_URL = os.getenv('DATABASE_URL')

def migrate_full_data():
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
        
        # Обрабатываем данные
        print("🔄 Processing data...")
        
        # Обрабатываем JSON поля
        json_columns = ['interest_signals', 'signals']
        for col in json_columns:
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda x: x if isinstance(x, str) else str(x) if pd.notna(x) else None
                )
        
        # Обрабатываем timestamps
        timestamp_columns = ['scraped_at', 'published_at', 'updated_at', 'ai_verification_date', 'created_at']
        for col in timestamp_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # Обрабатываем tsvector (если есть)
        if 'search_vector' in df.columns:
            df['search_vector'] = df['search_vector'].apply(
                lambda x: x if isinstance(x, str) else str(x) if pd.notna(x) else None
            )
        
        print(f"📊 Processed data shape: {df.shape}")
        
        # Очищаем staging таблицу
        print("🧹 Clearing staging table...")
        with staging_engine.begin() as conn:
            conn.execute(text("DELETE FROM public.places"))
            print("✅ Staging table cleared")
        
        # Загружаем данные в staging
        print("📤 Loading data to staging...")
        df.to_sql("places", staging_engine, if_exists="append", index=False, method='multi', chunksize=1000)
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
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(migrate_full_data())
