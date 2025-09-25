#!/usr/bin/env python3
"""
Скрипт для пересборки всех фотографий в базе данных с новым алгоритмом
"""

import os
import sys
import logging
from datetime import datetime

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.core.db import SessionLocal
from apps.places.models import Place
from apps.places.workers.ai_editor import AIEditorAgent

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def rebuild_all_photos():
    """Пересборка всех фотографий в базе данных"""
    logger.info("🔄 Начинаем пересборку всех фотографий в базе данных")
    
    db = SessionLocal()
    try:
        # Получаем все места с Google Place ID (исключаем тестовые данные)
        places = db.query(Place).filter(
            Place.gmaps_place_id.isnot(None),
            Place.gmaps_place_id != 'mock_place_1705'
        ).all()
        
        total_places = len(places)
        logger.info(f"📊 Найдено {total_places} мест для обработки")
        
        if total_places == 0:
            logger.warning("❌ Нет мест для обработки")
            return
        
        # Создаем AI Editor Agent
        agent = AIEditorAgent()
        
        processed_count = 0
        success_count = 0
        error_count = 0
        
        for i, place in enumerate(places, 1):
            logger.info(f"\n--- Обработка {i}/{total_places}: {place.name} ---")
            logger.info(f"Google Place ID: {place.gmaps_place_id}")
            
            try:
                # Получаем новую фотографию с улучшенным алгоритмом
                new_photo_url = agent._search_real_place_images(place)
                
                if new_photo_url:
                    # Обновляем фотографию в базе данных
                    place.picture_url = new_photo_url
                    place.updated_at = datetime.now()
                    
                    # Обновляем данные AI-агента
                    place.ai_verified = 'true'
                    place.ai_verification_date = datetime.now()
                    place.ai_verification_data = f'{{"photo_updated": true, "photo_url": "{new_photo_url}", "algorithm": "improved_photo_selection"}}'
                    
                    db.commit()
                    
                    success_count += 1
                    logger.info(f"✅ Фотография обновлена: {new_photo_url[:50]}...")
                else:
                    error_count += 1
                    logger.warning(f"❌ Не удалось найти фотографию для {place.name}")
                
                processed_count += 1
                
                # Показываем прогресс каждые 10 мест
                if i % 10 == 0:
                    logger.info(f"📈 Прогресс: {i}/{total_places} ({i/total_places*100:.1f}%)")
                
            except Exception as e:
                error_count += 1
                logger.error(f"❌ Ошибка обработки {place.name}: {e}")
                continue
        
        # Итоговая статистика
        logger.info(f"\n{'='*60}")
        logger.info("📈 ИТОГОВАЯ СТАТИСТИКА ПЕРЕСБОРКИ")
        logger.info(f"{'='*60}")
        logger.info(f"Всего обработано: {processed_count}")
        logger.info(f"Успешно обновлено: {success_count}")
        logger.info(f"Ошибок: {error_count}")
        logger.info(f"Процент успеха: {success_count/processed_count*100:.1f}%")
        
        # Показываем примеры обновленных фотографий
        logger.info(f"\nПримеры обновленных фотографий:")
        updated_places = db.query(Place).filter(
            Place.ai_verification_data.like('%photo_updated%')
        ).order_by(Place.updated_at.desc()).limit(5).all()
        
        for place in updated_places:
            logger.info(f"  {place.name}: {place.picture_url[:50]}...")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        db.rollback()
    finally:
        db.close()


def test_photo_quality():
    """Тестирование качества выбранных фотографий"""
    logger.info("\n🔍 Тестирование качества выбранных фотографий")
    
    db = SessionLocal()
    try:
        # Получаем несколько обновленных мест
        places = db.query(Place).filter(
            Place.ai_verification_data.like('%photo_updated%')
        ).limit(5).all()
        
        for place in places:
            logger.info(f"\n--- {place.name} ---")
            logger.info(f"Фотография: {place.picture_url}")
            
            # Проверяем качество URL
            if 'googleusercontent.com' in place.picture_url:
                logger.info("✅ Качественная фотография Google Places")
            elif 'unsplash.com' in place.picture_url:
                logger.info("⚠️  Заглушка Unsplash")
            else:
                logger.info("❓ Неизвестный источник")
    
    finally:
        db.close()


def main():
    """Главная функция"""
    logger.info("🎯 Запуск пересборки всех фотографий")
    
    # Пересборка фотографий
    rebuild_all_photos()
    
    # Тестирование качества
    test_photo_quality()


if __name__ == "__main__":
    main()
