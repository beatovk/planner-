#!/usr/bin/env python3
"""
Проверяем почему SearchService не возвращает правильные signals для MTCH
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.core.db import get_db
from apps.places.services.search import create_search_service

def main():
    """Проверяем SearchService"""
    print("ПРОВЕРКА SEARCHSERVICE")
    print("=" * 50)
    
    db = next(get_db())
    search_service = create_search_service(db)
    
    # Тестируем поиск matcha
    results = search_service.search_places(
        query="matcha",
        limit=20,
        user_lat=13.743407,
        user_lng=100.561428
    )
    
    print(f"Найдено мест: {len(results)}")
    print()
    
    # Ищем MTCH в результатах
    mtch_results = [r for r in results if 'mtch' in r['name'].lower()]
    
    print(f"MTCH в результатах: {len(mtch_results)}")
    for result in mtch_results:
        print(f"  Место: {result['name']}")
        print(f"    ID: {result.get('id')}")
        print(f"    Distance: {result.get('distance_m')}м")
        print(f"    Signals: {result.get('signals', {})}")
        hq = result.get('signals', {}).get('hq_experience', False)
        quality = result.get('signals', {}).get('quality_score', 0.0)
        print(f"    hq_experience: {hq}")
        print(f"    quality_score: {quality}")
        print()
    
    # Проверяем FTS поиск напрямую
    print("ПРОВЕРКА FTS ПОИСКА")
    print("=" * 50)
    
    fts_results = search_service._fts_search_pg(
        query="matcha",
        limit=20,
        offset=0,
        user_lat=13.743407,
        user_lng=100.561428,
        area=None,
        radius_m=None
    )
    
    print(f"FTS результаты: {len(fts_results)}")
    
    # Ищем MTCH в FTS результатах
    fts_mtch = [r for r in fts_results if 'mtch' in r['name'].lower()]
    
    print(f"MTCH в FTS: {len(fts_mtch)}")
    for result in fts_mtch:
        print(f"  Место: {result['name']}")
        print(f"    ID: {result.get('id')}")
        print(f"    Distance: {result.get('distance_m')}м")
        print(f"    Signals: {result.get('signals', {})}")
        hq = result.get('signals', {}).get('hq_experience', False)
        quality = result.get('signals', {}).get('quality_score', 0.0)
        print(f"    hq_experience: {hq}")
        print(f"    quality_score: {quality}")
        print()
    
    # Проверяем Netflix-style поиск
    print("ПРОВЕРКА NETFLIX-STYLE ПОИСКА")
    print("=" * 50)
    
    netflix_results = search_service._netflix_style_search(
        query="matcha",
        limit=20,
        offset=0,
        user_lat=13.743407,
        user_lng=100.561428,
        radius_m=None,
        sort="relevance",
        area=None
    )
    
    print(f"Netflix результаты: {len(netflix_results)}")
    
    # Ищем MTCH в Netflix результатах
    netflix_mtch = [r for r in netflix_results if 'mtch' in r['name'].lower()]
    
    print(f"MTCH в Netflix: {len(netflix_mtch)}")
    for result in netflix_mtch:
        print(f"  Место: {result['name']}")
        print(f"    ID: {result.get('id')}")
        print(f"    Distance: {result.get('distance_m')}м")
        print(f"    Signals: {result.get('signals', {})}")
        hq = result.get('signals', {}).get('hq_experience', False)
        quality = result.get('signals', {}).get('quality_score', 0.0)
        print(f"    hq_experience: {hq}")
        print(f"    quality_score: {quality}")
        print()

if __name__ == "__main__":
    main()
