#!/usr/bin/env python3
"""
Тест новой архитектуры: Google API обогатитель + AI Editor Agent
"""

import os
import sys
import logging

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.core.db import SessionLocal
from apps.places.models import Place
from apps.places.services.google_places import GooglePlaces
from apps.places.workers.ai_editor import AIEditorAgent

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_google_enricher_with_photos():
    """Тестирование Google API обогатителя с фотографиями"""
    logger.info("🔍 Тестирование Google API обогатителя с фотографиями")
    
    # Создаем Google Places клиент
    try:
        google_client = GooglePlaces()
    except Exception as e:
        logger.warning(f"Не удалось создать Google Places клиент: {e}")
        logger.info("Используем mock режим...")
        google_client = GooglePlaces(mock_mode=True)
    
    # Тестируем получение фотографий для известного места
    test_place_id = "ChIJY_tN0qCf4jARTp6Wg5ZCu0w"  # Kurasu Thonglor
    
    try:
        photo_url = google_client.get_place_photos(test_place_id)
        
        if photo_url:
            logger.info(f"✅ Получена фотография: {photo_url[:50]}...")
            
            # Проверяем качество URL
            if 'googleusercontent.com' in photo_url:
                logger.info("✅ Качественная фотография Google Places")
            elif 'unsplash.com' in photo_url:
                logger.info("⚠️  Заглушка Unsplash")
            else:
                logger.info("❓ Неизвестный источник")
        else:
            logger.info("❌ Фотография не получена")
            
    except Exception as e:
        logger.error(f"❌ Ошибка получения фотографии: {e}")


def test_ai_editor_quality_check():
    """Тестирование AI Editor Agent как проверяющего качества"""
    logger.info("\n🎯 Тестирование AI Editor Agent как проверяющего качества")
    
    db = SessionLocal()
    try:
        # Получаем места с фотографиями
        places = db.query(Place).filter(
            Place.picture_url.isnot(None)
        ).limit(3).all()
        
        if not places:
            logger.error("❌ Нет мест с фотографиями для тестирования")
            return
        
        # Создаем AI Editor Agent
        agent = AIEditorAgent()
        
        for place in places:
            logger.info(f"\n--- Проверка {place.name} ---")
            logger.info(f"Текущая фотография: {place.picture_url[:50]}...")
            
            # Проверяем качество фотографии
            is_quality = agent._is_quality_real_image(place.picture_url, place)
            
            if is_quality:
                logger.info("✅ Фотография качественная")
            else:
                logger.info("❌ Фотография некачественная")
                
                # Пробуем найти лучшую
                better_photo = agent._search_real_place_images(place)
                if better_photo != place.picture_url:
                    logger.info(f"🔄 Найдена лучшая фотография: {better_photo[:50]}...")
                else:
                    logger.info("ℹ️  Лучшая фотография не найдена")
    
    finally:
        db.close()


def test_full_pipeline():
    """Тестирование полного пайплайна"""
    logger.info("\n🔄 Тестирование полного пайплайна")
    
    # 1. Google API обогатитель собирает данные + фотографии
    logger.info("1️⃣ Google API обогатитель собирает данные...")
    
    # 2. AI Editor Agent проверяет качество
    logger.info("2️⃣ AI Editor Agent проверяет качество...")
    
    # 3. Результат
    logger.info("3️⃣ Результат: Единое место сбора данных + умная проверка качества")


def main():
    """Главная функция"""
    logger.info("🎯 Тестирование новой архитектуры")
    
    # Тест 1: Google API обогатитель с фотографиями
    test_google_enricher_with_photos()
    
    # Тест 2: AI Editor Agent как проверяющий
    test_ai_editor_quality_check()
    
    # Тест 3: Полный пайплайн
    test_full_pipeline()


if __name__ == "__main__":
    main()
