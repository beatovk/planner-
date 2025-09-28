#!/usr/bin/env python3
"""
Check database schemas
"""
import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print("❌ DATABASE_URL not set")
    exit(1)

engine = create_engine(DATABASE_URL)

try:
    with engine.begin() as conn:
        # Проверяем все схемы
        all_schemas = conn.execute(text("SELECT schema_name FROM information_schema.schemata ORDER BY schema_name")).fetchall()
        print(f'📋 All schemas: {[s[0] for s in all_schemas]}')
        
        # Проверяем существование схемы epx
        epx_exists = conn.execute(text("SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = 'epx')")).scalar()
        print(f'🔍 epx schema exists: {epx_exists}')
        
        if epx_exists:
            # Проверяем таблицы в epx
            epx_tables = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'epx'")).fetchall()
            print(f'📊 Tables in epx: {[t[0] for t in epx_tables]}')
        else:
            print('❌ epx schema does not exist - need to create it')

except Exception as e:
    print(f"❌ Error: {e}")
