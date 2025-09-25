#!/usr/bin/env python3
"""
Улучшенный тест AI Editor Agent с исправленной логикой
"""

import os
import sys
import logging
from datetime import datetime

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.core.db import SessionLocal
from apps.places.models import Place

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def simulate_ai_editor_processing(place: Place) -> dict:
    """Симуляция обработки AI Editor Agent"""
    
    result = {
        "place_id": place.id,
        "name": place.name,
        "category": place.category,
        "updates": [],
        "issues_fixed": [],
        "quality_improved": False
    }
    
    # 1. Проверяем и дополняем ценовой уровень
    if not place.price_level:
        # Умное определение на основе категории
        category = place.category.lower() if place.category else ""
        
        if "bar" in category or "nightclub" in category:
            new_price_level = 3
        elif "restaurant" in category or "cafe" in category:
            new_price_level = 2
        else:
            new_price_level = 2
        
        result["updates"].append(f"price_level: None -> {new_price_level}")
        result["issues_fixed"].append("price_level")
        result["quality_improved"] = True
    
    # 2. Проверяем и дополняем теги
    if not place.tags_csv:
        # Умные теги на основе категории
        category = place.category.lower() if place.category else ""
        
        if "bar" in category or "nightclub" in category:
            new_tags = "bar,nightlife,drinks"
        elif "restaurant" in category or "cafe" in category:
            new_tags = "restaurant,food,dining"
        elif "entertainment" in category:
            new_tags = "entertainment,fun,activity"
        else:
            new_tags = "restaurant,food,thai"
        
        result["updates"].append(f"tags_csv: None -> {new_tags}")
        result["issues_fixed"].append("tags")
        result["quality_improved"] = True
    
    # 3. Проверяем и дополняем изображения
    if not place.picture_url:
        # Placeholder изображения по категории
        category = place.category.lower() if place.category else ""
        
        if "restaurant" in category:
            new_image = "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=400"
        elif "bar" in category or "nightclub" in category:
            new_image = "https://images.unsplash.com/photo-1514933651103-005eec06c04b?w=400"
        elif "cafe" in category:
            new_image = "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=400"
        else:
            new_image = "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=400"
        
        result["updates"].append(f"picture_url: None -> {new_image[:50]}...")
        result["issues_fixed"].append("picture")
        result["quality_improved"] = True
    
    # 4. Проверяем часы работы
    if not place.hours_json:
        # Простые часы работы
        default_hours = {
            "monday": "9:00-22:00",
            "tuesday": "9:00-22:00", 
            "wednesday": "9:00-22:00",
            "thursday": "9:00-22:00",
            "friday": "9:00-23:00",
            "saturday": "9:00-23:00",
            "sunday": "9:00-22:00"
        }
        
        result["updates"].append(f"hours_json: None -> {len(default_hours)} days")
        result["issues_fixed"].append("hours")
        result["quality_improved"] = True
    
    return result


def test_improved_ai_editor():
    """Тестирование улучшенного AI Editor Agent"""
    logger.info("🤖 Тестирование улучшенного AI Editor Agent")
    
    db = SessionLocal()
    try:
        # Получаем 10 мест со статусом published
        places = db.query(Place).filter(
            Place.processing_status == 'published'
        ).order_by(Place.id.desc()).limit(10).all()
        
        if not places:
            logger.error("❌ Нет мест для анализа")
            return
        
        logger.info(f"📊 Анализируем {len(places)} мест")
        
        results = []
        total_improvements = 0
        
        for i, place in enumerate(places, 1):
            logger.info(f"\n--- Место {i}: {place.name} ---")
            
            # Анализируем до обработки
            before_issues = []
            if not place.price_level:
                before_issues.append("price_level")
            if not place.tags_csv:
                before_issues.append("tags")
            if not place.picture_url:
                before_issues.append("picture")
            if not place.hours_json:
                before_issues.append("hours")
            
            logger.info(f"Проблем до обработки: {len(before_issues)}")
            
            # Симулируем обработку AI Editor
            result = simulate_ai_editor_processing(place)
            results.append(result)
            
            # Выводим результаты
            if result["updates"]:
                logger.info(f"✅ Обновления: {len(result['updates'])}")
                for update in result["updates"]:
                    logger.info(f"  - {update}")
                total_improvements += len(result["updates"])
            else:
                logger.info("ℹ️ Обновления не требуются")
        
        # Итоговая статистика
        logger.info(f"\n{'='*60}")
        logger.info("📈 ИТОГОВАЯ СТАТИСТИКА")
        logger.info(f"{'='*60}")
        
        places_improved = sum(1 for r in results if r["quality_improved"])
        total_updates = sum(len(r["updates"]) for r in results)
        
        logger.info(f"Мест улучшено: {places_improved}/{len(places)} ({places_improved/len(places)*100:.1f}%)")
        logger.info(f"Всего обновлений: {total_updates}")
        logger.info(f"Среднее обновлений на место: {total_updates/len(places):.1f}")
        
        # Топ исправленных проблем
        all_issues_fixed = []
        for result in results:
            all_issues_fixed.extend(result["issues_fixed"])
        
        issue_counts = {}
        for issue in all_issues_fixed:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
        
        logger.info(f"\nТоп исправленных проблем:")
        for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {issue}: {count} раз")
        
        # Показываем примеры улучшений
        logger.info(f"\nПримеры улучшений:")
        for result in results[:3]:
            if result["updates"]:
                logger.info(f"  {result['name']}: {', '.join(result['issues_fixed'])}")
        
    finally:
        db.close()


def main():
    """Главная функция"""
    logger.info("🎯 Запуск тестирования улучшенного AI Editor Agent")
    test_improved_ai_editor()


if __name__ == "__main__":
    main()
