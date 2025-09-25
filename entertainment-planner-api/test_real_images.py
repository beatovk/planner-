#!/usr/bin/env python3
"""
Тест поиска реальных изображений мест
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


def test_real_image_search():
    """Тестирование поиска реальных изображений"""
    logger.info("🖼️ Тестирование поиска реальных изображений")
    
    db = SessionLocal()
    try:
        # Получаем 5 мест для тестирования
        places = db.query(Place).filter(
            Place.processing_status == 'published'
        ).order_by(Place.id.desc()).limit(5).all()
        
        if not places:
            logger.error("❌ Нет мест для тестирования")
            return
        
        # Создаем AI Editor Agent
        agent = AIEditorAgent()
        
        results = []
        for i, place in enumerate(places, 1):
            logger.info(f"\n--- Тест {i}: {place.name} ({place.category}) ---")
            
            # Тестируем поиск изображений
            image_result = agent._find_quality_images(place)
            
            result = {
                "name": place.name,
                "category": place.category,
                "found": image_result.get("found", False),
                "url": image_result.get("url", ""),
                "source": image_result.get("source", ""),
                "quality": image_result.get("quality", "")
            }
            
            results.append(result)
            
            # Выводим результат
            if result["found"]:
                logger.info(f"✅ Найдено изображение")
                logger.info(f"   URL: {result['url'][:80]}...")
                logger.info(f"   Источник: {result['source']}")
                logger.info(f"   Качество: {result['quality']}")
            else:
                logger.info(f"❌ Изображение не найдено")
        
        # Итоговая статистика
        logger.info(f"\n{'='*60}")
        logger.info("📈 ИТОГОВАЯ СТАТИСТИКА")
        logger.info(f"{'='*60}")
        
        found_count = sum(1 for r in results if r["found"])
        real_images = sum(1 for r in results if r["found"] and r["source"] == "real_search")
        placeholder_images = sum(1 for r in results if r["found"] and r["source"] == "placeholder")
        
        logger.info(f"Всего протестировано: {len(results)}")
        logger.info(f"Изображений найдено: {found_count} ({found_count/len(results)*100:.1f}%)")
        logger.info(f"Реальных изображений: {real_images}")
        logger.info(f"Placeholder изображений: {placeholder_images}")
        
        # Показываем примеры
        logger.info(f"\nПримеры найденных изображений:")
        for result in results:
            if result["found"]:
                logger.info(f"  {result['name']}: {result['url'][:50]}... ({result['source']})")
        
    finally:
        db.close()


def main():
    """Главная функция"""
    logger.info("🎯 Запуск тестирования поиска реальных изображений")
    test_real_image_search()


if __name__ == "__main__":
    main()
