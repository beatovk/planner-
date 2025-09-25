#!/usr/bin/env python3
"""
Скрипт для проверки настройки PostgreSQL после применения исправлений.
Запускать только после настройки PostgreSQL и миграции данных.
"""

import os
import sys
from pathlib import Path

def test_config():
    """Тест 1: Проверка конфигурации"""
    print("🔧 Тест 1: Проверка конфигурации...")
    try:
        from apps.core.config import settings
        print(f"✅ Settings загружены: database_url = {settings.database_url}")
        return True
    except Exception as e:
        print(f"❌ Ошибка загрузки настроек: {e}")
        return False

def test_database_url():
    """Тест 2: Проверка DATABASE_URL"""
    print("\n🔧 Тест 2: Проверка DATABASE_URL...")
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL не установлен в переменных окружения")
        print("💡 Установите: export DATABASE_URL='postgresql+psycopg://ep:ep@localhost:5432/ep'")
        return False
    
    if not (db_url.startswith("postgresql://") or db_url.startswith("postgresql+psycopg://")):
        print(f"❌ DATABASE_URL не PostgreSQL: {db_url}")
        print("💡 Ожидается: postgresql+psycopg://user:pass@host:port/db")
        return False
    
    print(f"✅ DATABASE_URL корректный: {db_url}")
    return True

def test_database_connection():
    """Тест 3: Проверка подключения к БД"""
    print("\n🔧 Тест 3: Проверка подключения к БД...")
    try:
        from apps.core.db import engine, DB_URL
        print(f"✅ Engine создан: {DB_URL.split('@')[-1] if '@' in DB_URL else 'masked'}")
        
        with engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text("SELECT 1")).scalar()
            print(f"✅ Подключение работает: {result}")
            
            # Проверяем таблицу places
            places_count = conn.execute(text("SELECT COUNT(*) FROM places")).scalar()
            print(f"✅ Таблица places: {places_count} записей")
            
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return False

def test_api_health():
    """Тест 4: Проверка health check API"""
    print("\n🔧 Тест 4: Проверка health check API...")
    try:
        from apps.api.main import health_db
        result = health_db()
        
        if result.get("ok"):
            print(f"✅ Health check: OK")
            print(f"   Driver: {result.get('driver')}")
            print(f"   Places: {result.get('places_count')}")
            print(f"   DSN: {result.get('dsn')}")
            return True
        else:
            print(f"❌ Health check failed: {result.get('error')}")
            return False
    except Exception as e:
        print(f"❌ Ошибка health check: {e}")
        return False

def main():
    """Главная функция тестирования"""
    print("🚀 Тестирование настройки PostgreSQL после исправлений\n")
    
    tests = [
        test_config,
        test_database_url,
        test_database_connection,
        test_api_health
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 Результат: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 Все тесты пройдены! Система готова к работе.")
        return 0
    else:
        print("⚠️  Некоторые тесты не пройдены. Проверьте настройку PostgreSQL.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
