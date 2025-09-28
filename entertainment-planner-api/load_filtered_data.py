#!/usr/bin/env python3
"""
Load filtered data from source to staging (only matching columns)
"""
import os
import pandas as pd
from sqlalchemy import create_engine, text

# Исходная база данных
SOURCE_URL = "postgresql+psycopg://postgres:1234@localhost:5432/ep"
# Staging база данных
STAGING_URL = os.getenv('DATABASE_URL')

def load_filtered_data():
    if not STAGING_URL:
        print("❌ STAGING_URL not set")
        return 1
    
    print("🔄 Connecting to source database...")
    source_engine = create_engine(SOURCE_URL)
    
    print("🔄 Connecting to staging database...")
    staging_engine = create_engine(STAGING_URL)
    
    try:
        # Получаем структуру staging таблицы
        print("📋 Getting staging table structure...")
        with staging_engine.begin() as conn:
            result = conn.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'places'
                ORDER BY ordinal_position
            """))
            staging_columns = {row[0]: row[1] for row in result}
            print(f"📊 Staging columns: {list(staging_columns.keys())}")
        
        # Читаем данные из исходной базы
        print("📥 Reading data from source...")
        df = pd.read_sql_table("places", source_engine)
        print(f"📊 Read {len(df)} rows from source")
        
        # Фильтруем только нужные колонки
        print("🔍 Filtering columns...")
        available_columns = [col for col in staging_columns.keys() if col in df.columns]
        missing_columns = [col for col in staging_columns.keys() if col not in df.columns]
        
        print(f"✅ Available columns: {available_columns}")
        if missing_columns:
            print(f"⚠️  Missing columns: {missing_columns}")
        
        # Оставляем только доступные колонки
        df_filtered = df[available_columns].copy()
        
        # Обрабатываем signals (конвертируем в JSONB)
        if 'signals' in df_filtered.columns:
            print("🔄 Processing signals column...")
            df_filtered['signals'] = df_filtered['signals'].apply(
                lambda x: x if isinstance(x, str) else str(x) if pd.notna(x) else None
            )
        
        # Обрабатываем timestamps
        for col in ['created_at', 'updated_at']:
            if col in df_filtered.columns:
                df_filtered[col] = pd.to_datetime(df_filtered[col], errors='coerce')
        
        print(f"📊 Filtered data shape: {df_filtered.shape}")
        
        # Очищаем staging таблицу
        print("🧹 Clearing staging table...")
        with staging_engine.begin() as conn:
            conn.execute(text("DELETE FROM public.places"))
            print("✅ Staging table cleared")
        
        # Загружаем данные в staging
        print("📤 Loading data to staging...")
        df_filtered.to_sql("places", staging_engine, if_exists="append", index=False)
        print(f"✅ Loaded {len(df_filtered)} rows to staging")
        
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
    exit(load_filtered_data())
