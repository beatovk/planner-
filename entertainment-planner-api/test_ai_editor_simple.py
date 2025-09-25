#!/usr/bin/env python3
"""
Упрощенный тест AI Editor Agent - только проверка логики без GPT
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


def analyze_place_data(place: Place) -> dict:
    """Анализ данных места без GPT"""
    
    analysis = {
        "place_id": place.id,
        "name": place.name,
        "category": place.category,
        "issues": [],
        "suggestions": [],
        "missing_fields": [],
        "quality_score": 0
    }
    
    # Проверяем основные поля
    if not place.name or not place.name.strip():
        analysis["issues"].append("Отсутствует название")
        analysis["missing_fields"].append("name")
    else:
        analysis["quality_score"] += 1
    
    if not place.category or not place.category.strip():
        analysis["issues"].append("Отсутствует категория")
        analysis["missing_fields"].append("category")
    else:
        analysis["quality_score"] += 1
    
    if not place.description_full and not place.summary:
        analysis["issues"].append("Отсутствует описание")
        analysis["missing_fields"].append("description")
    else:
        analysis["quality_score"] += 1
    
    if not place.tags_csv:
        analysis["issues"].append("Отсутствуют теги")
        analysis["missing_fields"].append("tags")
    else:
        analysis["quality_score"] += 1
    
    if not place.address:
        analysis["issues"].append("Отсутствует адрес")
        analysis["missing_fields"].append("address")
    else:
        analysis["quality_score"] += 1
    
    if not place.lat or not place.lng:
        analysis["issues"].append("Отсутствуют координаты")
        analysis["missing_fields"].append("coordinates")
    else:
        analysis["quality_score"] += 1
    
    if not place.price_level:
        analysis["issues"].append("Отсутствует ценовой уровень")
        analysis["missing_fields"].append("price_level")
    else:
        analysis["quality_score"] += 1
    
    if not place.hours_json:
        analysis["issues"].append("Отсутствуют часы работы")
        analysis["missing_fields"].append("hours")
    else:
        analysis["quality_score"] += 1
    
    if not place.picture_url:
        analysis["issues"].append("Отсутствует изображение")
        analysis["missing_fields"].append("picture")
    else:
        analysis["quality_score"] += 1
    
    # Определяем общее качество
    total_fields = 9
    quality_percentage = (analysis["quality_score"] / total_fields) * 100
    
    if quality_percentage >= 80:
        analysis["overall_quality"] = "excellent"
    elif quality_percentage >= 60:
        analysis["overall_quality"] = "good"
    elif quality_percentage >= 40:
        analysis["overall_quality"] = "fair"
    else:
        analysis["overall_quality"] = "poor"
    
    # Предложения по улучшению
    if "description" in analysis["missing_fields"]:
        analysis["suggestions"].append("Добавить описание через GPT")
    
    if "tags" in analysis["missing_fields"]:
        analysis["suggestions"].append("Сгенерировать теги через GPT")
    
    if "coordinates" in analysis["missing_fields"]:
        analysis["suggestions"].append("Получить координаты через Google API")
    
    if "picture" in analysis["missing_fields"]:
        analysis["suggestions"].append("Найти изображение через веб-поиск")
    
    return analysis


def test_10_places():
    """Тестирование 10 мест"""
    logger.info("🔍 Анализ 10 последних мест из БД")
    
    db = SessionLocal()
    try:
        # Получаем 10 последних мест со статусом published
        places = db.query(Place).filter(
            Place.processing_status == 'published'
        ).order_by(Place.id.desc()).limit(10).all()
        
        if not places:
            logger.error("❌ Нет мест для анализа")
            return
        
        logger.info(f"📊 Найдено {len(places)} мест для анализа")
        
        results = []
        for i, place in enumerate(places, 1):
            logger.info(f"\n--- Место {i}: {place.name} ---")
            
            analysis = analyze_place_data(place)
            results.append(analysis)
            
            # Выводим краткий анализ
            logger.info(f"Качество: {analysis['overall_quality']} ({analysis['quality_score']}/9)")
            logger.info(f"Проблемы: {len(analysis['issues'])}")
            logger.info(f"Недостающие поля: {', '.join(analysis['missing_fields'])}")
            
            if analysis['issues']:
                logger.info(f"Основные проблемы: {analysis['issues'][:3]}")
        
        # Итоговая статистика
        logger.info(f"\n{'='*60}")
        logger.info("📈 ИТОГОВАЯ СТАТИСТИКА")
        logger.info(f"{'='*60}")
        
        quality_counts = {}
        total_issues = 0
        total_missing = 0
        
        for result in results:
            quality = result['overall_quality']
            quality_counts[quality] = quality_counts.get(quality, 0) + 1
            total_issues += len(result['issues'])
            total_missing += len(result['missing_fields'])
        
        logger.info(f"Качество мест:")
        for quality, count in quality_counts.items():
            logger.info(f"  {quality}: {count}")
        
        logger.info(f"Среднее количество проблем: {total_issues / len(results):.1f}")
        logger.info(f"Среднее количество недостающих полей: {total_missing / len(results):.1f}")
        
        # Топ проблем
        all_issues = []
        for result in results:
            all_issues.extend(result['issues'])
        
        issue_counts = {}
        for issue in all_issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
        
        logger.info(f"\nТоп проблем:")
        for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            logger.info(f"  {issue}: {count} раз")
        
    finally:
        db.close()


def main():
    """Главная функция"""
    logger.info("🎯 Запуск упрощенного теста AI Editor Agent")
    test_10_places()


if __name__ == "__main__":
    main()
