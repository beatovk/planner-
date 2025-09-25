#!/usr/bin/env python3
"""
Скрипт для изменения владельца таблицы places на пользователя ep
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

def main():
    # Подключаемся как postgres для изменения владельца
    database_url = "postgresql+psycopg://postgres:1234@localhost:5432/ep"
    
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            print("✅ Подключение к БД как postgres успешно")
            
            # Меняем владельца таблицы places
            print("Меняем владельца таблицы places...")
            conn.execute(text("ALTER TABLE places OWNER TO ep;"))
            conn.commit()
            print("✅ Владелец изменен на ep")
            
            # Проверяем владельца
            result = conn.execute(text("""
                SELECT table_name, table_owner 
                FROM information_schema.tables 
                WHERE table_name = 'places'
            """))
            owner_info = list(result)
            print(f"Владелец таблицы places: {owner_info}")
            
    except SQLAlchemyError as e:
        print(f"❌ Ошибка БД: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
