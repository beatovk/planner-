#!/usr/bin/env python3
"""
Check database size and table contents
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
        # Проверяем количество записей в places
        places_count = conn.execute(text('SELECT COUNT(*) FROM places')).scalar()
        print(f'📊 Places count: {places_count}')
        
        # Проверяем размер базы данных
        db_size = conn.execute(text('SELECT pg_size_pretty(pg_database_size(current_database()))')).scalar()
        print(f'💾 Database size: {db_size}')
        
        # Проверяем все таблицы в public схеме
        tables = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")).fetchall()
        print(f'📋 Tables in public schema: {[t[0] for t in tables]}')
        
        # Проверяем размер каждой таблицы
        print('\n📏 Table sizes:')
        for table in tables:
            table_name = table[0]
            try:
                size_result = conn.execute(text(f"SELECT pg_size_pretty(pg_total_relation_size('public.{table_name}'))")).scalar()
                print(f'  {table_name}: {size_result}')
            except Exception as e:
                print(f'  {table_name}: Error - {e}')
        
        # Проверяем содержимое places
        if places_count > 0:
            print(f'\n🔍 Sample places data:')
            sample_data = conn.execute(text('SELECT id, name, category, created_at FROM places LIMIT 5')).fetchall()
            for row in sample_data:
                print(f'  ID {row[0]}: {row[1]} ({row[2]}) - {row[3]}')
        
        # Проверяем epx схему
        try:
            epx_tables = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'epx'")).fetchall()
            print(f'\n📋 Tables in epx schema: {[t[0] for t in epx_tables]}')
            
            if epx_tables:
                for table in epx_tables:
                    table_name = table[0]
                    try:
                        count = conn.execute(text(f"SELECT COUNT(*) FROM epx.{table_name}")).scalar()
                        size_result = conn.execute(text(f"SELECT pg_size_pretty(pg_total_relation_size('epx.{table_name}'))")).scalar()
                        print(f'  epx.{table_name}: {count} rows, {size_result}')
                    except Exception as e:
                        print(f'  epx.{table_name}: Error - {e}')
        except Exception as e:
            print(f'❌ Error checking epx schema: {e}')

except Exception as e:
    print(f"❌ Error: {e}")
