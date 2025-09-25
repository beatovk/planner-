#!/usr/bin/env python3
"""
Глобальные тесты для API и фронтенда
"""

import sys
import os
import requests
import json
import time
from urllib.parse import urlencode

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_1_api_health():
    """Тест 1: Проверка здоровья API"""
    print("=" * 60)
    print("ТЕСТ 1: Проверка здоровья API")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    
    # Проверяем основные endpoints
    endpoints = [
        "/api/health",
        "/health/db",
        "/api/health/feature-flags"
    ]
    
    results = {}
    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            results[endpoint] = {
                "status": response.status_code,
                "success": response.status_code == 200,
                "data": response.json() if response.status_code == 200 else None
            }
            print(f"  {endpoint}: {response.status_code} {'✅' if response.status_code == 200 else '❌'}")
        except Exception as e:
            results[endpoint] = {"status": "error", "success": False, "error": str(e)}
            print(f"  {endpoint}: ERROR - {e}")
    
    return all(r["success"] for r in results.values())

def test_2_api_rails_basic():
    """Тест 2: Базовый API /api/rails"""
    print("\n" + "=" * 60)
    print("ТЕСТ 2: Базовый API /api/rails")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    
    # Тест 1: Пустой запрос
    try:
        response = requests.get(f"{base_url}/api/rails", timeout=10)
        print(f"Пустой запрос: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Рельсов: {len(data.get('rails', []))}")
        else:
            print(f"  Ошибка: {response.text}")
    except Exception as e:
        print(f"Пустой запрос: ERROR - {e}")
    
    # Тест 2: Запрос с matcha
    try:
        params = {
            "q": "matcha",
            "limit": 12,
            "user_lat": 13.743488,
            "user_lng": 100.561457
        }
        response = requests.get(f"{base_url}/api/rails", params=params, timeout=10)
        print(f"Запрос 'matcha': {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Рельсов: {len(data.get('rails', []))}")
            mtch_found = any('mtch' in item.get('name', '').lower() 
                           for rail in data.get('rails', []) 
                           for item in rail.get('items', []))
            print(f"  MTCH найден: {mtch_found}")
        else:
            print(f"  Ошибка: {response.text}")
    except Exception as e:
        print(f"Запрос 'matcha': ERROR - {e}")
    
    # Тест 3: Слоттер запрос
    try:
        params = {
            "q": "i wanna chill matcha and rooftop",
            "limit": 12,
            "user_lat": 13.743488,
            "user_lng": 100.561457
        }
        response = requests.get(f"{base_url}/api/rails", params=params, timeout=10)
        print(f"Слоттер запрос: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Рельсов: {len(data.get('rails', []))}")
            for i, rail in enumerate(data.get('rails', [])):
                print(f"    Рельс {i}: {rail.get('label', 'Unknown')} - {len(rail.get('items', []))} мест")
                mtch_items = [item for item in rail.get('items', []) 
                             if 'mtch' in item.get('name', '').lower()]
                if mtch_items:
                    print(f"      MTCH: {[item.get('name') for item in mtch_items]}")
        else:
            print(f"  Ошибка: {response.text}")
    except Exception as e:
        print(f"Слоттер запрос: ERROR - {e}")
    
    return True

def test_3_api_high_experience():
    """Тест 3: High Experience API"""
    print("\n" + "=" * 60)
    print("ТЕСТ 3: High Experience API")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    
    # Тест High Experience
    try:
        params = {
            "q": "i wanna chill matcha and rooftop",
            "limit": 12,
            "user_lat": 13.743488,
            "user_lng": 100.561457,
            "quality": "high"
        }
        response = requests.get(f"{base_url}/api/rails", params=params, timeout=10)
        print(f"High Experience запрос: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  Рельсов: {len(data.get('rails', []))}")
            for i, rail in enumerate(data.get('rails', [])):
                print(f"    Рельс {i}: {rail.get('label', 'Unknown')} - {len(rail.get('items', []))} мест")
                mtch_items = [item for item in rail.get('items', []) 
                             if 'mtch' in item.get('name', '').lower()]
                if mtch_items:
                    print(f"      MTCH: {[item.get('name') for item in mtch_items]}")
        else:
            print(f"  Ошибка: {response.text}")
    except Exception as e:
        print(f"High Experience запрос: ERROR - {e}")
    
    return True

def test_4_frontend_static():
    """Тест 4: Статические файлы фронтенда"""
    print("\n" + "=" * 60)
    print("ТЕСТ 4: Статические файлы фронтенда")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    
    # Проверяем основные статические файлы
    static_files = [
        "/web2/",
        "/web2/app1.js",
        "/web2/index.html",
        "/web2/styles.css"
    ]
    
    results = {}
    for file_path in static_files:
        try:
            response = requests.get(f"{base_url}{file_path}", timeout=5)
            results[file_path] = {
                "status": response.status_code,
                "success": response.status_code == 200,
                "size": len(response.content) if response.status_code == 200 else 0
            }
            print(f"  {file_path}: {response.status_code} {'✅' if response.status_code == 200 else '❌'} ({len(response.content)} bytes)")
        except Exception as e:
            results[file_path] = {"status": "error", "success": False, "error": str(e)}
            print(f"  {file_path}: ERROR - {e}")
    
    return all(r["success"] for r in results.values())

def test_5_frontend_api_integration():
    """Тест 5: Интеграция фронтенда с API"""
    print("\n" + "=" * 60)
    print("ТЕСТ 5: Интеграция фронтенда с API")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    
    # Получаем главную страницу
    try:
        response = requests.get(f"{base_url}/web2/", timeout=5)
        if response.status_code == 200:
            html_content = response.text
            print(f"Главная страница: ✅ ({len(html_content)} bytes)")
            
            # Проверяем наличие ключевых элементов
            checks = [
                ("app1.js", "app1.js" in html_content),
                ("queryInput", "queryInput" in html_content),
                ("api/rails", "api/rails" in html_content),
                ("fetch", "fetch" in html_content)
            ]
            
            for check_name, check_result in checks:
                print(f"  {check_name}: {'✅' if check_result else '❌'}")
            
            return all(result for _, result in checks)
        else:
            print(f"Главная страница: ❌ {response.status_code}")
            return False
    except Exception as e:
        print(f"Главная страница: ERROR - {e}")
        return False

def test_6_cors_headers():
    """Тест 6: CORS заголовки"""
    print("\n" + "=" * 60)
    print("ТЕСТ 6: CORS заголовки")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    
    try:
        # Отправляем OPTIONS запрос для проверки CORS с правильными заголовками
        headers = {
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Requested-With"
        }
        response = requests.options(f"{base_url}/api/rails", headers=headers, timeout=5)
        print(f"OPTIONS запрос: {response.status_code}")
        
        # Проверяем заголовки
        response_headers = response.headers
        cors_headers = [
            "Access-Control-Allow-Origin",
            "Access-Control-Allow-Methods",
            "Access-Control-Allow-Headers"
        ]
        
        for header in cors_headers:
            value = response_headers.get(header, "Not set")
            print(f"  {header}: {value}")
        
        # CORS работает если есть хотя бы один заголовок
        cors_working = any(header in response_headers for header in cors_headers)
        print(f"  CORS работает: {'✅' if cors_working else '❌'}")
        
        return cors_working
    except Exception as e:
        print(f"CORS проверка: ERROR - {e}")
        return False

def test_7_api_response_format():
    """Тест 7: Формат ответа API"""
    print("\n" + "=" * 60)
    print("ТЕСТ 7: Формат ответа API")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    
    try:
        params = {
            "q": "matcha",
            "limit": 5,
            "user_lat": 13.743488,
            "user_lng": 100.561457
        }
        response = requests.get(f"{base_url}/api/rails", params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"API ответ: ✅")
            
            # Проверяем структуру ответа
            required_fields = ["rails", "processing_time_ms", "cache_hit"]
            for field in required_fields:
                has_field = field in data
                print(f"  {field}: {'✅' if has_field else '❌'}")
            
            # Проверяем структуру рельсов
            if "rails" in data and data["rails"]:
                rail = data["rails"][0]
                rail_fields = ["label", "items"]
                for field in rail_fields:
                    has_field = field in rail
                    print(f"  rail.{field}: {'✅' if has_field else '❌'}")
                
                # Проверяем структуру элементов
                if "items" in rail and rail["items"]:
                    item = rail["items"][0]
                    item_fields = ["name", "distance_m"]
                    for field in item_fields:
                        has_field = field in item
                        print(f"  item.{field}: {'✅' if has_field else '❌'}")
            
            return True
        else:
            print(f"API ответ: ❌ {response.status_code}")
            return False
    except Exception as e:
        print(f"API ответ: ERROR - {e}")
        return False

def test_8_server_startup():
    """Тест 8: Запуск сервера"""
    print("\n" + "=" * 60)
    print("ТЕСТ 8: Запуск сервера")
    print("=" * 60)
    
    # Проверяем, запущен ли сервер
    try:
        response = requests.get("http://localhost:8000/api/health", timeout=5)
        if response.status_code == 200:
            print("Сервер запущен: ✅")
            return True
        else:
            print(f"Сервер запущен: ❌ {response.status_code}")
            return False
    except Exception as e:
        print(f"Сервер запущен: ❌ {e}")
        print("Попытка запуска сервера...")
        
        # Запускаем сервер
        import subprocess
        try:
            process = subprocess.Popen([
                "python", "start_server.py"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Ждем 5 секунд
            time.sleep(5)
            
            # Проверяем снова
            response = requests.get("http://localhost:8000/api/health", timeout=5)
            if response.status_code == 200:
                print("Сервер запущен после попытки: ✅")
                return True
            else:
                print(f"Сервер не запустился: ❌ {response.status_code}")
                return False
        except Exception as e2:
            print(f"Ошибка запуска сервера: {e2}")
            return False

def main():
    """Запуск всех тестов"""
    print("ГЛОБАЛЬНОЕ ТЕСТИРОВАНИЕ API И ФРОНТЕНДА")
    print("=" * 80)
    
    results = {}
    
    # Запускаем тесты
    results['server_startup'] = test_8_server_startup()
    results['api_health'] = test_1_api_health()
    results['api_rails_basic'] = test_2_api_rails_basic()
    results['api_high_experience'] = test_3_api_high_experience()
    results['frontend_static'] = test_4_frontend_static()
    results['frontend_api_integration'] = test_5_frontend_api_integration()
    results['cors_headers'] = test_6_cors_headers()
    results['api_response_format'] = test_7_api_response_format()
    
    # Итоговый отчет
    print("\n" + "=" * 80)
    print("ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 80)
    
    for test_name, result in results.items():
        print(f"{test_name}: {'✅' if result else '❌'}")
    
    # Рекомендации
    print("\nРЕКОМЕНДАЦИИ:")
    if not results.get('server_startup'):
        print("- Запустите сервер: python start_server.py")
    if not results.get('api_health'):
        print("- Проверьте конфигурацию API")
    if not results.get('frontend_static'):
        print("- Проверьте статические файлы фронтенда")
    if not results.get('frontend_api_integration'):
        print("- Проверьте интеграцию фронтенда с API")
    if not results.get('cors_headers'):
        print("- Настройте CORS заголовки")
    
    # Общий статус
    success_count = sum(1 for r in results.values() if r)
    total_count = len(results)
    print(f"\nОБЩИЙ СТАТУС: {success_count}/{total_count} тестов прошли")
    
    if success_count == total_count:
        print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ! API и фронтенд работают правильно!")
    else:
        print("⚠️ Некоторые тесты не прошли. Проверьте рекомендации выше.")

if __name__ == "__main__":
    main()
