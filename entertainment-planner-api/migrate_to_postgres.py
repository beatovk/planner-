#!/usr/bin/env python3
"""
Migrate data from SQLite to PostgreSQL
"""
import os
import sys
from sqlalchemy import create_engine, text, inspect
import pandas as pd

def migrate_data():
    # SQLite source
    sqlite_url = "sqlite:///entertainment.db"
    sqlite_engine = create_engine(sqlite_url)
    
    # PostgreSQL destination
    postgres_url = os.getenv('DATABASE_URL')
    if not postgres_url:
        print("❌ DATABASE_URL not set")
        return 1
    
    postgres_engine = create_engine(postgres_url)
    
    try:
        # Check if places table exists in SQLite
        with sqlite_engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='places'"))
            if not result.fetchone():
                print("❌ places table not found in SQLite")
                return 1
            
            # Get table info
            inspector = inspect(sqlite_engine)
            columns = inspector.get_columns('places')
            print(f"📋 Found {len(columns)} columns in places table")
            
            # Read data from SQLite
            print("📥 Reading data from SQLite...")
            df = pd.read_sql("SELECT * FROM places", sqlite_engine)
            print(f"📊 Found {len(df)} records")
            
            if len(df) == 0:
                print("⚠️  No data to migrate")
                return 0
            
            # Create table in PostgreSQL
            print("🏗️  Creating table in PostgreSQL...")
            with postgres_engine.begin() as conn:
                # Drop if exists
                conn.execute(text("DROP TABLE IF EXISTS places CASCADE"))
                
                # Create table with proper schema
                create_sql = """
                CREATE TABLE places (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(256),
                    category VARCHAR(64),
                    summary TEXT,
                    description TEXT,
                    tags_csv TEXT,
                    lat FLOAT,
                    lng FLOAT,
                    picture_url TEXT,
                    gmaps_place_id VARCHAR(256),
                    gmaps_url TEXT,
                    rating FLOAT,
                    processing_status VARCHAR(16) DEFAULT 'published',
                    signals JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
                conn.execute(text(create_sql))
                print("✅ Table created")
            
            # Insert data
            print("📤 Inserting data into PostgreSQL...")
            with postgres_engine.begin() as conn:
                # Convert DataFrame to PostgreSQL format
                df_clean = df.copy()
                
                # Handle NaN values
                df_clean = df_clean.fillna('')
                
                # Insert data
                df_clean.to_sql('places', postgres_engine, if_exists='append', index=False, method='multi')
                print(f"✅ Inserted {len(df_clean)} records")
            
            # Now create the materialized view
            print("🏗️  Creating materialized view...")
            with postgres_engine.begin() as conn:
                # Read and execute create_mv.sql
                with open('create_mv.sql', 'r') as f:
                    sql_content = f.read()
                
                statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
                for stmt in statements:
                    if stmt:
                        print(f"Executing: {stmt[:50]}...")
                        conn.execute(text(stmt))
                
                print("✅ Materialized view created")
            
            print("🎉 Migration completed successfully!")
            return 0
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(migrate_data())
