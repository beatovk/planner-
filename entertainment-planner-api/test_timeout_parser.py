#!/usr/bin/env python3
"""
Тестовый скрипт для парсера TimeOut Bangkok
"""
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.places.ingestion.timeout_adapter import TimeOutAdapter
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_timeout_parser():
    """Тестируем парсер на реальной странице TimeOut"""
    
    # URL для тестирования
    test_url = "https://www.timeout.com/bangkok/restaurants/bangkoks-best-new-cafes-of-2025"
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ПАРСЕРА TIMEOUT BANGKOK")
    print("=" * 60)
    print(f"URL: {test_url}")
    print()
    
    # Создаем адаптер
    adapter = TimeOutAdapter()
    
    try:
        # Парсим места
        print("Начинаем парсинг...")
        places = adapter.parse_places_from_list(test_url)
        
        print(f"\n✅ Успешно спарсено мест: {len(places)}")
        print()
        
        # Показываем результаты
        for i, place in enumerate(places[:5], 1):  # Показываем первые 5
            print(f"--- МЕСТО {i} ---")
            print(f"Название: {place.get('name', 'N/A')}")
            print(f"Категория: {place.get('category', 'N/A')}")
            print(f"Район: {place.get('area', 'N/A')}")
            print(f"Адрес: {place.get('address', 'N/A')}")
            print(f"Часы: {place.get('hours_text', 'N/A')}")
            print(f"Google Maps: {place.get('gmaps_url', 'N/A')}")
            print(f"Картинка: {place.get('picture_url', 'N/A')}")
            
            description = place.get('description_full', '')
            if description:
                print(f"Описание: {description[:150]}{'...' if len(description) > 150 else ''}")
            
            print(f"Источник: {place.get('source_url', 'N/A')}")
            print()
        
        # Статистика
        print("=" * 60)
        print("СТАТИСТИКА")
        print("=" * 60)
        
        with_address = sum(1 for p in places if p.get('address'))
        with_hours = sum(1 for p in places if p.get('hours_text'))
        with_gmaps = sum(1 for p in places if p.get('gmaps_url'))
        with_images = sum(1 for p in places if p.get('picture_url'))
        with_description = sum(1 for p in places if p.get('description_full'))
        
        print(f"Всего мест: {len(places)}")
        print(f"С адресом: {with_address} ({with_address/len(places)*100:.1f}%)")
        print(f"С часами работы: {with_hours} ({with_hours/len(places)*100:.1f}%)")
        print(f"С Google Maps: {with_gmaps} ({with_gmaps/len(places)*100:.1f}%)")
        print(f"С картинками: {with_images} ({with_images/len(places)*100:.1f}%)")
        print(f"С описанием: {with_description} ({with_description/len(places)*100:.1f}%)")
        
        return places
        
    except Exception as e:
        logger.error(f"Ошибка при тестировании парсера: {e}")
        import traceback
        traceback.print_exc()
        return []


if __name__ == "__main__":
    test_timeout_parser()
