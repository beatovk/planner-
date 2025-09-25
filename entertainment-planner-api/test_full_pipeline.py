#!/usr/bin/env python3
"""
Полный цикл обработки мест: загрузка → саммаризация → обогащение Google API → AI Editor проверка
"""

import os
import sys
import csv
import logging
from datetime import datetime

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.core.db import SessionLocal
from apps.places.models import Place
from apps.places.services.google_places import GooglePlaces
from apps.places.workers.ai_editor import AIEditorAgent

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_places_from_csv(csv_file_path: str) -> list:
    """Загрузка мест из CSV файла"""
    logger.info(f"📥 Загрузка мест из {csv_file_path}")
    
    places = []
    
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file, delimiter='\t')
            
            for row in reader:
                place_data = {
                    'name': row.get('name', '').strip(),
                    'description_full': row.get('description_full', '').strip()
                }
                
                if place_data['name'] and place_data['description_full']:
                    places.append(place_data)
        
        logger.info(f"✅ Загружено {len(places)} мест из CSV")
        return places
        
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки CSV: {e}")
        return []


def insert_places_to_db(places_data: list) -> list:
    """Вставка мест в базу данных"""
    logger.info("💾 Вставка мест в базу данных")
    
    db = SessionLocal()
    inserted_places = []
    
    try:
        for place_data in places_data:
            # Проверяем, не существует ли уже такое место
            existing = db.query(Place).filter(Place.name == place_data['name']).first()
            if existing:
                logger.info(f"⚠️  Место уже существует: {place_data['name']}")
                continue
            
            # Создаем новое место
            place = Place(
                name=place_data['name'],
                description_full=place_data['description_full'],
                source='csv_import',
                source_url=f"csv_import_{place_data['name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                scraped_at=datetime.now(),
                processing_status='new'
            )
            
            db.add(place)
            inserted_places.append(place)
        
        db.commit()
        logger.info(f"✅ Вставлено {len(inserted_places)} новых мест в БД")
        return inserted_places
        
    except Exception as e:
        logger.error(f"❌ Ошибка вставки в БД: {e}")
        db.rollback()
        return []
    finally:
        db.close()


def summarize_places(places: list) -> list:
    """Саммаризация мест с помощью GPT"""
    logger.info("🤖 Саммаризация мест с помощью GPT")
    
    from apps.places.workers.gpt_normalizer import GPTNormalizerWorker
    
    summarizer = GPTNormalizerWorker()
    summarized_places = []
    
    db = SessionLocal()
    try:
        for place in places:
            try:
                logger.info(f"Саммаризация: {place.name}")
                
                # Получаем место из БД для работы с сессией
                db_place = db.query(Place).filter(Place.id == place.id).first()
                if not db_place:
                    logger.warning(f"Место не найдено в БД: {place.name}")
                    continue
                
                # Саммаризируем место
                summarizer._process_place(db_place, db)
                
                if db_place.processing_status == 'summarized':
                    summarized_places.append(db_place)
                    logger.info(f"✅ Саммаризировано: {db_place.name}")
                else:
                    logger.warning(f"❌ Ошибка саммаризации {db_place.name}: {db_place.last_error}")
                    
            except Exception as e:
                logger.error(f"❌ Ошибка саммаризации {place.name}: {e}")
        
        db.commit()
        logger.info(f"✅ Сохранено {len(summarized_places)} саммаризированных мест")
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения саммаризации: {e}")
        db.rollback()
    finally:
        db.close()
    
    return summarized_places


def enrich_with_google_api(places: list) -> list:
    """Обогащение мест данными Google API"""
    logger.info("🌍 Обогащение данными Google API")
    
    # Создаем Google Places клиент
    try:
        google_client = GooglePlaces()
    except Exception as e:
        logger.warning(f"Не удалось создать Google Places клиент: {e}")
        logger.info("Используем mock режим...")
        google_client = GooglePlaces(mock_mode=True)
    
    enriched_places = []
    
    for place in places:
        try:
            logger.info(f"Обогащение: {place.name}")
            
            # Обогащаем место
            from apps.places.commands.enrich_google import enrich_one_place
            success, message = enrich_one_place(place, google_client)
            
            if success:
                place.processing_status = 'published'
                enriched_places.append(place)
                logger.info(f"✅ Обогащено: {place.name}")
            else:
                logger.warning(f"❌ Ошибка обогащения {place.name}: {message}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка обогащения {place.name}: {e}")
    
    # Сохраняем изменения в БД
    db = SessionLocal()
    try:
        for place in enriched_places:
            db.merge(place)
        db.commit()
        logger.info(f"✅ Сохранено {len(enriched_places)} обогащенных мест")
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения обогащения: {e}")
        db.rollback()
    finally:
        db.close()
    
    return enriched_places


def ai_editor_verification(places: list) -> list:
    """Проверка и доработка мест AI Editor Agent"""
    logger.info("🎯 Проверка AI Editor Agent")
    
    ai_editor = AIEditorAgent()
    verified_places = []
    
    for place in places:
        try:
            logger.info(f"Проверка AI Editor: {place.name}")
            
            # Проверяем место
            result = ai_editor._process_place(place)
            
            if result:
                verified_places.append(place)
                logger.info(f"✅ Проверено AI Editor: {place.name}")
            else:
                logger.warning(f"❌ Ошибка проверки AI Editor: {place.name}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки AI Editor {place.name}: {e}")
    
    return verified_places


def show_results(places: list):
    """Показ результатов обработки"""
    logger.info("\n" + "="*60)
    logger.info("📊 РЕЗУЛЬТАТЫ ОБРАБОТКИ")
    logger.info("="*60)
    
    for i, place in enumerate(places, 1):
        logger.info(f"\n--- Место {i}: {place.name} ---")
        logger.info(f"Статус: {place.processing_status}")
        logger.info(f"Категория: {place.category}")
        logger.info(f"Теги: {place.tags_csv}")
        logger.info(f"Цена: {place.price_level}")
        logger.info(f"Координаты: {place.lat}, {place.lng}")
        logger.info(f"Google Place ID: {place.gmaps_place_id}")
        logger.info(f"Фотография: {place.picture_url[:50] if place.picture_url else 'Нет'}...")
        logger.info(f"AI проверено: {place.ai_verified}")
        
        if place.summary:
            logger.info(f"Саммари: {place.summary[:100]}...")


def main():
    """Главная функция полного пайплайна"""
    logger.info("🚀 Запуск полного цикла обработки мест")
    
    # Путь к CSV файлу
    csv_file_path = "test_places.csv"
    
    # Этап 1: Загрузка из CSV
    places_data = load_places_from_csv(csv_file_path)
    if not places_data:
        logger.error("❌ Не удалось загрузить данные из CSV")
        return
    
    # Этап 2: Вставка в БД
    inserted_places = insert_places_to_db(places_data)
    if not inserted_places:
        logger.error("❌ Не удалось вставить места в БД")
        return
    
    # Этап 3: Саммаризация
    summarized_places = summarize_places(inserted_places)
    if not summarized_places:
        logger.error("❌ Не удалось саммаризировать места")
        return
    
    # Этап 4: Обогащение Google API
    enriched_places = enrich_with_google_api(summarized_places)
    if not enriched_places:
        logger.error("❌ Не удалось обогатить места Google API")
        return
    
    # Этап 5: AI Editor проверка
    verified_places = ai_editor_verification(enriched_places)
    
    # Показ результатов
    show_results(verified_places)
    
    logger.info(f"\n🎉 Полный цикл завершен! Обработано {len(verified_places)} мест")


if __name__ == "__main__":
    main()
