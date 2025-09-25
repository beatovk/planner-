#!/usr/bin/env python3
"""
Тест выбора лучших фотографий с интерьером и едой
"""

import os
import sys
import logging

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.core.db import SessionLocal
from apps.places.models import Place
from apps.places.workers.ai_editor import AIEditorAgent

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_photo_selection():
    """Тестирование выбора лучших фотографий"""
    logger.info("📸 Тестирование выбора фотографий с интерьером и едой")
    
    db = SessionLocal()
    try:
        # Получаем места с Google Place ID
        places = db.query(Place).filter(
            Place.processing_status == 'published',
            Place.gmaps_place_id.isnot(None),
            Place.gmaps_place_id != 'mock_place_1705'  # Исключаем тестовые данные
        ).limit(3).all()
        
        if not places:
            logger.error("❌ Нет мест с Google Place ID для тестирования")
            return
        
        # Создаем AI Editor Agent
        agent = AIEditorAgent()
        
        results = []
        for i, place in enumerate(places, 1):
            logger.info(f"\n--- Тест {i}: {place.name} ---")
            logger.info(f"Google Place ID: {place.gmaps_place_id}")
            
            # Тестируем получение фотографий через Google Places API
            try:
                photo_url = agent._search_real_place_images(place)
                
                result = {
                    "name": place.name,
                    "place_id": place.gmaps_place_id,
                    "found": photo_url is not None,
                    "url": photo_url or "",
                    "source": "google_places" if photo_url else "none"
                }
                
                results.append(result)
                
                if photo_url:
                    logger.info(f"✅ Найдена фотография Google Places")
                    logger.info(f"   URL: {photo_url[:80]}...")
                else:
                    logger.info(f"❌ Фотография не найдена")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка получения фотографии: {e}")
                results.append({
                    "name": place.name,
                    "place_id": place.gmaps_place_id,
                    "found": False,
                    "url": "",
                    "source": "error"
                })
        
        # Итоговая статистика
        logger.info(f"\n{'='*60}")
        logger.info("📈 ИТОГОВАЯ СТАТИСТИКА")
        logger.info(f"{'='*60}")
        
        found_count = sum(1 for r in results if r["found"])
        total_count = len(results)
        
        logger.info(f"Всего протестировано: {total_count}")
        logger.info(f"Фотографий найдено: {found_count} ({found_count/total_count*100:.1f}%)")
        
        # Показываем примеры найденных фотографий
        logger.info(f"\nПримеры найденных фотографий:")
        for result in results:
            if result["found"]:
                logger.info(f"  {result['name']}: {result['url'][:50]}...")
        
        # Показываем места без фотографий
        no_photos = [r for r in results if not r["found"]]
        if no_photos:
            logger.info(f"\nМеста без фотографий:")
            for result in no_photos:
                logger.info(f"  {result['name']} (Place ID: {result['place_id']})")
        
    finally:
        db.close()


def test_photo_scoring():
    """Тестирование системы оценки фотографий"""
    logger.info("\n🎯 Тестирование системы оценки фотографий")
    
    # Тестовые данные фотографий
    test_photos = [
        {
            "name": "test_photo_1",
            "widthPx": 1920,
            "heightPx": 1080,
            "authorAttributions": [{"displayName": "Restaurant Owner"}]
        },
        {
            "name": "test_photo_2", 
            "widthPx": 800,
            "heightPx": 600,
            "authorAttributions": [{"displayName": "Food Photography"}]
        },
        {
            "name": "test_photo_3",
            "widthPx": 1200,
            "heightPx": 800,
            "authorAttributions": [{"displayName": "Interior Design"}]
        },
        {
            "name": "test_photo_4",
            "widthPx": 600,
            "heightPx": 400,
            "authorAttributions": [{"displayName": "Exterior Building"}]
        }
    ]
    
    agent = AIEditorAgent()
    place = Place(name="Test Restaurant", category="restaurant")
    
    try:
        best_photo = agent._select_best_photo(test_photos, place)
        
        if best_photo:
            logger.info(f"✅ Выбрана лучшая фотография: {best_photo['name']}")
            logger.info(f"   Размер: {best_photo['widthPx']}x{best_photo['heightPx']}")
            logger.info(f"   Автор: {best_photo['authorAttributions'][0]['displayName']}")
        else:
            logger.info(f"❌ Фотография не выбрана")
            
    except Exception as e:
        logger.error(f"❌ Ошибка выбора фотографии: {e}")


def main():
    """Главная функция"""
    logger.info("🎯 Запуск тестирования выбора фотографий")
    
    # Тест 1: Выбор лучших фотографий
    test_photo_selection()
    
    # Тест 2: Система оценки
    test_photo_scoring()


if __name__ == "__main__":
    main()
