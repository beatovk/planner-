#!/usr/bin/env python3
"""
Check and create epx schema if needed
"""
import os
from sqlalchemy import create_engine, text

def check_and_create_epx():
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        print("❌ DATABASE_URL not set")
        return 1
    
    engine = create_engine(DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # Check if epx schema exists
            has_epx = conn.execute(text("SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname='epx')")).scalar()
            print(f"Схема epx существует: {has_epx}")
            
            if not has_epx:
                # Create epx schema
                conn.execute(text("CREATE SCHEMA IF NOT EXISTS epx;"))
                conn.commit()
                print("✅ Схема epx создана")
            else:
                print("✅ Схема epx уже существует")
                
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    exit(check_and_create_epx())
