#!/usr/bin/env python3
"""
Check staging database via proxy
"""
import os
from sqlalchemy import create_engine, text

# Подключение через прокси
PROXY_URL = "postgresql+psycopg://postgres:dM5Ru9XD0B16a0c@127.0.0.1:5439/postgres"

def check_database():
    engine = create_engine(PROXY_URL)
    
    try:
        with engine.begin() as conn:
            # Проверяем таблицу places
            places_count = conn.execute(text("SELECT COUNT(*) FROM public.places")).scalar()
            print(f"📊 Places count: {places_count}")
            
            # Проверяем MV
            mv_count = conn.execute(text("SELECT COUNT(*) FROM epx.places_search_mv")).scalar()
            print(f"📊 MV count: {mv_count}")
            
            # Проверяем derived flags
            flags = conn.execute(text("""
                SELECT 
                    SUM(is_chill::int) as chill,
                    SUM(is_romantic::int) as romantic,
                    SUM(is_cinema::int) as cinema
                FROM epx.places_search_mv
            """)).fetchone()
            
            print(f"🎯 Derived flags: chill={flags[0]}, romantic={flags[1]}, cinema={flags[2]}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_database()
