#!/usr/bin/env python3
"""Тест исправленного парсера TimeOut"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.places.ingestion.timeout_adapter import TimeOutAdapter

def test_parser():
    """Тестируем исправленный парсер на одном месте"""
    adapter = TimeOutAdapter()
    
    # Тестируем на одном месте
    test_url = "https://www.timeout.com/bangkok/restaurants/kurasu-thonglor-sukhumvit-57"
    
    print(f"Тестируем парсер на: {test_url}")
    print("=" * 80)
    
    result = adapter.parse_detail_page(test_url)
    
    if result:
        print("✅ Парсер успешно извлек данные:")
        print(f"Название: {result.get('name')}")
        print(f"Категория: {result.get('category')}")
        print(f"Район: {result.get('area')}")
        print(f"Описание: {result.get('description_full')[:200]}..." if result.get('description_full') else "Описание: НЕ НАЙДЕНО")
        print(f"Адрес: {result.get('address')}")
        print(f"Часы работы: {result.get('hours_text')}")
        print(f"Координаты: lat={result.get('lat')}, lng={result.get('lng')}")
        print(f"Картинка: {result.get('picture_url')}")
        print(f"Google Maps: {result.get('gmaps_url')}")
    else:
        print("❌ Парсер не смог извлечь данные")

if __name__ == "__main__":
    test_parser()
