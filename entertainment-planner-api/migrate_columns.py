#!/usr/bin/env python3
"""
Миграция для добавления колонок search_vector и signals в таблицу places
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

def main():
    # Настройка подключения
    database_url = os.getenv("DATABASE_URL", "postgresql+psycopg://ep:ep@localhost:5432/ep")
    
    try:
        # Создаем подключение
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            print("✅ Подключение к БД успешно")
            
            # Проверяем, существуют ли колонки
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'places' 
                AND column_name IN ('search_vector', 'signals')
            """))
            existing_columns = [row[0] for row in result]
            
            print(f"Существующие колонки: {existing_columns}")
            
            # Добавляем search_vector если не существует
            if 'search_vector' not in existing_columns:
                print("Добавляем колонку search_vector...")
                conn.execute(text("ALTER TABLE places ADD COLUMN search_vector tsvector;"))
                conn.commit()
                print("✅ Колонка search_vector добавлена")
            else:
                print("✅ Колонка search_vector уже существует")
            
            # Добавляем signals если не существует
            if 'signals' not in existing_columns:
                print("Добавляем колонку signals...")
                conn.execute(text("ALTER TABLE places ADD COLUMN signals JSONB;"))
                conn.commit()
                print("✅ Колонка signals добавлена")
            else:
                print("✅ Колонка signals уже существует")
            
            # Создаем индексы
            print("Создаем индексы...")
            try:
                conn.execute(text("CREATE INDEX IF NOT EXISTS places_search_gin_idx ON places USING gin (search_vector);"))
                print("✅ Индекс places_search_gin_idx создан")
            except Exception as e:
                print(f"⚠️ Индекс places_search_gin_idx: {e}")
            
            try:
                conn.execute(text("CREATE INDEX IF NOT EXISTS places_signals_idx ON places USING gin (signals);"))
                print("✅ Индекс places_signals_idx создан")
            except Exception as e:
                print(f"⚠️ Индекс places_signals_idx: {e}")
            
            # Заполняем search_vector для существующих записей
            print("Заполняем search_vector...")
            conn.execute(text("""
                UPDATE places
                SET search_vector = to_tsvector(
                    'simple',
                    unaccent(coalesce(name,'') || ' ' || coalesce(category,'') || ' ' ||
                             coalesce(tags_csv,'') || ' ' || coalesce(summary,''))
                )
                WHERE search_vector IS NULL;
            """))
            conn.commit()
            print("✅ search_vector заполнен")
            
            # Проверяем результат
            result = conn.execute(text("SELECT COUNT(*) FROM places WHERE search_vector IS NOT NULL;"))
            count = result.scalar()
            print(f"✅ Записей с search_vector: {count}")
            
            print("\n🎉 Миграция завершена успешно!")
            
    except SQLAlchemyError as e:
        print(f"❌ Ошибка БД: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
