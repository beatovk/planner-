#!/usr/bin/env python3
"""
Скрипт для выдачи прав пользователю ep на таблицу places
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

def main():
    # Подключаемся как postgres для выдачи прав
    database_url = "postgresql+psycopg://postgres:1234@localhost:5432/ep"
    
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            print("✅ Подключение к БД как postgres успешно")
            
            # Даем права на таблицу places
            print("Выдаем права на таблицу places...")
            conn.execute(text("GRANT ALL PRIVILEGES ON TABLE places TO ep;"))
            conn.execute(text("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ep;"))
            conn.commit()
            print("✅ Права выданы")
            
            # Проверяем права
            result = conn.execute(text("""
                SELECT grantee, privilege_type 
                FROM information_schema.table_privileges 
                WHERE table_name = 'places' AND grantee = 'ep'
            """))
            privileges = list(result)
            print(f"Права пользователя ep: {privileges}")
            
    except SQLAlchemyError as e:
        print(f"❌ Ошибка БД: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
