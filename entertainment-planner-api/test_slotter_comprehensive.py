#!/usr/bin/env python3
"""
Комплексные тесты для выявления проблем со слоттером и High Experience
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.core.db import get_db
from apps.places.services.search import create_search_service
from apps.places.services.query_builder import create_query_builder
from apps.places.schemas.slots import Slot, SlotType
from apps.api.routes.compose import _compose_slotter_rails
import json

def test_1_fts_vs_fallback():
    """Тест 1: FTS vs Fallback поиск"""
    print("=" * 60)
    print("ТЕСТ 1: FTS vs Fallback поиск")
    print("=" * 60)
    
    db = next(get_db())
    search_service = create_search_service(db)
    
    query = "matcha"
    user_lat, user_lng = 13.743488, 100.561457
    
    # FTS поиск
    fts_results = search_service._fts_search_pg(
        query=query, limit=20, offset=0,
        user_lat=user_lat, user_lng=user_lng, area=None, radius_m=10000
    )
    
    # Fallback поиск
    fallback_results = search_service._netflix_style_search(
        query=query, limit=20, offset=0,
        user_lat=user_lat, user_lng=user_lng, radius_m=10000,
        sort="relevance", area=None
    )
    
    print(f"FTS результаты: {len(fts_results)}")
    print(f"Fallback результаты: {len(fallback_results)}")
    
    # Ищем MTCH
    fts_mtch = [p for p in fts_results if 'mtch' in p['name'].lower()]
    fallback_mtch = [p for p in fallback_results if 'mtch' in p['name'].lower()]
    
    print(f"MTCH в FTS: {len(fts_mtch)}")
    for p in fts_mtch:
        print(f"  - {p['name']} - {p.get('distance_m', 'N/A')}м - signals: {p.get('signals', {})}")
    
    print(f"MTCH в Fallback: {len(fallback_mtch)}")
    for p in fallback_mtch:
        print(f"  - {p['name']} - {p.get('distance_m', 'N/A')}м - signals: {p.get('signals', {})}")
    
    return len(fts_mtch) > 0, len(fallback_mtch) > 0

def test_2_search_places():
    """Тест 2: search_places (основной метод)"""
    print("\n" + "=" * 60)
    print("ТЕСТ 2: search_places (основной метод)")
    print("=" * 60)
    
    db = next(get_db())
    search_service = create_search_service(db)
    
    query = "matcha"
    user_lat, user_lng = 13.743488, 100.561457
    
    results = search_service.search_places(
        query=query, limit=20, user_lat=user_lat, user_lng=user_lng, radius_m=10000
    )
    
    print(f"search_places результаты: {len(results)}")
    
    mtch_results = [p for p in results if 'mtch' in p['name'].lower()]
    print(f"MTCH в search_places: {len(mtch_results)}")
    for p in mtch_results:
        print(f"  - {p['name']} - {p.get('distance_m', 'N/A')}м - signals: {p.get('signals', {})}")
    
    return len(mtch_results) > 0

def test_3_search_by_slot():
    """Тест 3: search_by_slot (слоттер)"""
    print("\n" + "=" * 60)
    print("ТЕСТ 3: search_by_slot (слоттер)")
    print("=" * 60)
    
    db = next(get_db())
    search_service = create_search_service(db)
    
    slot = Slot(
        type=SlotType.DRINK,
        canonical='matcha',
        label='Matcha drinks',
        confidence=0.9,
        matched_text='matcha',
        reason='matched drink:matcha',
        filters={'expands_to_tags': ['drink:matcha']}
    )
    
    results = search_service.search_by_slot(
        slot=slot, limit=20, user_lat=13.743488, user_lng=100.561457, radius_m=10000
    )
    
    print(f"search_by_slot результаты: {len(results)}")
    
    mtch_results = [p for p in results if 'mtch' in p['name'].lower()]
    print(f"MTCH в search_by_slot: {len(mtch_results)}")
    for p in mtch_results:
        print(f"  - {p['name']} - {p.get('distance_m', 'N/A')}м - signals: {p.get('signals', {})}")
        print(f"    hq_experience: {p.get('signals', {}).get('hq_experience', False)}")
    
    return len(mtch_results) > 0

async def test_4_slotter_rails():
    """Тест 4: _compose_slotter_rails (полный слоттер)"""
    print("\n" + "=" * 60)
    print("ТЕСТ 4: _compose_slotter_rails (полный слоттер)")
    print("=" * 60)
    
    db = next(get_db())
    
    # Импортируем функцию
    from apps.api.routes.compose import _compose_slotter_rails
    
    # Тестируем слоттер
    result = await _compose_slotter_rails(
        q="i wanna chill matcha and rooftop",
        area=None,
        user_lat=13.743488,
        user_lng=100.561457,
        quality_only=False,
        db=db
    )
    
    print(f"Слоттер рельсов: {len(result.rails)}")
    
    for i, rail in enumerate(result.rails):
        print(f"  Рельс {i}: {rail.label} - {len(rail.items)} мест")
        mtch_items = [item for item in rail.items if 'mtch' in item.name.lower()]
        if mtch_items:
            print(f"    MTCH в рельсе {i}: {len(mtch_items)}")
            for item in mtch_items:
                print(f"      - {item.name} - {getattr(item, 'distance_m', 'N/A')}м")
    
    return any('mtch' in item.name.lower() for rail in result.rails for item in rail.items)

async def test_5_high_experience():
    """Тест 5: High Experience режим"""
    print("\n" + "=" * 60)
    print("ТЕСТ 5: High Experience режим")
    print("=" * 60)
    
    db = next(get_db())
    
    # Тестируем High Experience
    result = await _compose_slotter_rails(
        q="i wanna chill matcha and rooftop",
        area=None,
        user_lat=13.743488,
        user_lng=100.561457,
        quality_only=True,  # High Experience
        db=db
    )
    
    print(f"High Experience рельсов: {len(result.rails)}")
    
    for i, rail in enumerate(result.rails):
        print(f"  Рельс {i}: {rail.label} - {len(rail.items)} мест")
        mtch_items = [item for item in rail.items if 'mtch' in item.name.lower()]
        if mtch_items:
            print(f"    MTCH в рельсе {i}: {len(mtch_items)}")
            for item in mtch_items:
                print(f"      - {item.name} - {getattr(item, 'distance_m', 'N/A')}м")
    
    return any('mtch' in item.name.lower() for rail in result.rails for item in rail.items)

def test_6_database_check():
    """Тест 6: Проверка базы данных"""
    print("\n" + "=" * 60)
    print("ТЕСТ 6: Проверка базы данных")
    print("=" * 60)
    
    db = next(get_db())
    
    # Проверяем места с MTCH
    from apps.places.models import Place
    mtch_places = db.query(Place).filter(Place.name.ilike('%mtch%')).all()
    
    print(f"MTCH мест в БД: {len(mtch_places)}")
    for place in mtch_places:
        print(f"  - {place.name} - {place.processing_status}")
        print(f"    Координаты: {place.lat}, {place.lng}")
        print(f"    Теги: {place.tags_csv}")
        print(f"    Signals: {place.signals}")
        print()
    
    # Проверяем материализованное представление
    from sqlalchemy import text
    mv_count = db.execute(text("SELECT COUNT(*) FROM epx.places_search_mv")).scalar()
    mtch_mv_count = db.execute(text("SELECT COUNT(*) FROM epx.places_search_mv WHERE name ILIKE '%mtch%'")).scalar()
    
    print(f"Записей в epx.places_search_mv: {mv_count}")
    print(f"MTCH записей в epx.places_search_mv: {mtch_mv_count}")
    
    return len(mtch_places) > 0, mtch_mv_count > 0

def test_7_api_endpoints():
    """Тест 7: API endpoints"""
    print("\n" + "=" * 60)
    print("ТЕСТ 7: API endpoints")
    print("=" * 60)
    
    import requests
    
    base_url = "http://localhost:8000"
    
    # Тест обычного поиска
    try:
        response = requests.get(f"{base_url}/api/rails", params={
            "q": "i wanna chill matcha and rooftop",
            "limit": 12,
            "user_lat": 13.743488,
            "user_lng": 100.561457
        })
        if response.status_code == 200:
            data = response.json()
            print(f"Обычный поиск: {len(data['rails'])} рельсов")
            mtch_found = any('mtch' in item['name'].lower() for rail in data['rails'] for item in rail['items'])
            print(f"MTCH найден в обычном поиске: {mtch_found}")
        else:
            print(f"Ошибка обычного поиска: {response.status_code}")
    except Exception as e:
        print(f"Ошибка обычного поиска: {e}")
    
    # Тест High Experience
    try:
        response = requests.get(f"{base_url}/api/rails", params={
            "q": "i wanna chill matcha and rooftop",
            "limit": 12,
            "user_lat": 13.743488,
            "user_lng": 100.561457,
            "quality": "high"
        })
        if response.status_code == 200:
            data = response.json()
            print(f"High Experience: {len(data['rails'])} рельсов")
            mtch_found = any('mtch' in item['name'].lower() for rail in data['rails'] for item in rail['items'])
            print(f"MTCH найден в High Experience: {mtch_found}")
        else:
            print(f"Ошибка High Experience: {response.status_code}")
    except Exception as e:
        print(f"Ошибка High Experience: {e}")

async def main():
    """Запуск всех тестов"""
    print("КОМПЛЕКСНОЕ ТЕСТИРОВАНИЕ СЛОТТЕРА И HIGH EXPERIENCE")
    print("=" * 80)
    
    results = {}
    
    # Запускаем тесты
    results['fts_vs_fallback'] = test_1_fts_vs_fallback()
    results['search_places'] = test_2_search_places()
    results['search_by_slot'] = test_3_search_by_slot()
    results['slotter_rails'] = await test_4_slotter_rails()
    results['high_experience'] = await test_5_high_experience()
    results['database_check'] = test_6_database_check()
    results['api_endpoints'] = test_7_api_endpoints()
    
    # Итоговый отчет
    print("\n" + "=" * 80)
    print("ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 80)
    
    for test_name, result in results.items():
        if isinstance(result, tuple):
            print(f"{test_name}: {'✅' if all(result) else '❌'} {result}")
        else:
            print(f"{test_name}: {'✅' if result else '❌'}")
    
    print("\nРЕКОМЕНДАЦИИ:")
    if not results.get('fts_vs_fallback', (False, False))[0]:
        print("- FTS поиск не находит MTCH")
    if not results.get('search_places'):
        print("- search_places не находит MTCH")
    if not results.get('search_by_slot'):
        print("- search_by_slot не находит MTCH")
    if not results.get('slotter_rails'):
        print("- Слоттер не находит MTCH")
    if not results.get('high_experience'):
        print("- High Experience не находит MTCH")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
