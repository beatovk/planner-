#!/usr/bin/env python3
"""
Тест получения фотографий через Google Places API
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


def test_google_places_photos():
    """Тестирование получения фотографий через Google Places API"""
    logger.info("📸 Тестирование Google Places API для фотографий")
    
    db = SessionLocal()
    try:
        # Получаем места с Google Place ID
        places = db.query(Place).filter(
            Place.processing_status == 'published',
            Place.gmaps_place_id.isnot(None)
        ).limit(5).all()
        
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
                photo_url = agent._get_google_place_photos(place.gmaps_place_id)
                
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


def test_google_photo_url():
    """Тестирование получения URL фотографии"""
    logger.info("\n🔗 Тестирование получения URL фотографии")
    
    # Реальный photo_name из Google Places API
    test_photo_name = "places/ChIJY_tN0qCf4jARTp6Wg5ZCu0w/photos/AciIO2e3xSApBFJcSspLe_0lo_hY_M_s_FP9yUn_KGGsbY8t3wl5T1asYUN88polFuEoAHtEWRsfd1NHIxXMpZixxEADCt3l6EZDn63thvXIZsIecAPDQnQv5tc91Xk9ZAJLVOMqa5MgDiDPD5pzY6Hm2ZsIkLNk_8B4wXUwuYbglIlGM99SRHHnJUon4mTb5A5O933LHD-yvSHhXejq7iJTzRr79jrbISpbJnF0P_SVHyzd3e2D0_w0ZO4OljNDnD67p2YAYYTQ4wbszhEyOoG2Ulcuot0vvZK-v3FZZsUz_7O2Qw"
    
    agent = AIEditorAgent()
    
    try:
        photo_url = agent._get_google_photo_url_new(test_photo_name, "AIzaSyBjExK9M7wOu929zQNbnlFJ8kjr-QreP6w")
        
        if photo_url:
            logger.info(f"✅ URL фотографии получен: {photo_url[:50]}...")
        else:
            logger.info(f"❌ URL фотографии не получен")
            
    except Exception as e:
        logger.error(f"❌ Ошибка получения URL: {e}")


def main():
    """Главная функция"""
    logger.info("🎯 Запуск тестирования Google Places API")
    
    # Тест 1: Получение фотографий мест
    test_google_places_photos()
    
    # Тест 2: Получение URL фотографии
    test_google_photo_url()


if __name__ == "__main__":
    main()
