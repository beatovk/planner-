#!/usr/bin/env python3
"""
Ручная обработка мест поэтапно
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

# Тестовые места из CSV
test_places = [
    {
        'name': 'Le Du',
        'description_full': 'Modern Thai tasting menus built on seasonal Thai produce and precise technique. The room feels intimate yet energetic. Flavors chase balance rather than blunt heat, layering herbs, citrus, and a measured sweetness over clean textures. Dishes land quickly from a focused kitchen, and staff help dial spice levels so first‑timers feel welcome. Portions are built for sharing, which makes it easy to sample across salads, grills, and a curry or two. Regulars know to mix a crunchy snack with one soup for contrast, then finish with something charcoal‑kissed.'
    },
    {
        'name': 'Sorn',
        'description_full': 'An ode to Southern Thai cuisine with long-simmered curries and rare coastal produce. The setting is elegant and the pacing is deliberate. Flavors chase balance rather than blunt heat, layering herbs, citrus, and a measured sweetness over clean textures. Dishes land quickly from a focused kitchen, and staff help dial spice levels so first‑timers feel welcome. Portions are built for sharing, which makes it easy to sample across salads, grills, and a curry or two. Regulars know to mix a crunchy snack with one soup for contrast, then finish with something charcoal‑kissed.'
    },
    {
        'name': 'Gaggan Anand',
        'description_full': 'Progressive Indian dining with playful storytelling and high-energy chef interaction. Dishes twist nostalgia into something new. Menus evolve with the market, so courses feel anchored in the season rather than locked to a script. Service keeps the pacing unhurried and conversational, giving room for stories about sourcing and technique. Pairings are thoughtful without being fussy, and non‑alcoholic options are treated with the same care as wine. Expect a calm room where details matter—glassware, lighting, and the small courtesies that make a night flow.'
    },
    {
        'name': 'Baan Tepa',
        'description_full': 'A garden-to-table Thai journey that foregrounds biodiversity and culinary craft. Guests move through a narrative of terroir and technique. Flavors chase balance rather than blunt heat, layering herbs, citrus, and a measured sweetness over clean textures. Dishes land quickly from a focused kitchen, and staff help dial spice levels so first‑timers feel welcome. Portions are built for sharing, which makes it easy to sample across salads, grills, and a curry or two. Regulars know to mix a crunchy snack with one soup for contrast, then finish with something charcoal‑kissed.'
    },
    {
        'name': 'Nusara',
        'description_full': 'An intimate, heirloom-inspired Thai restaurant that refines family recipes into a coursed experience. It feels like dinner in a gracious home. Menus evolve with the market, so courses feel anchored in the season rather than locked to a script. Service keeps the pacing unhurried and conversational, giving room for stories about sourcing and technique. Pairings are thoughtful without being fussy, and non‑alcoholic options are treated with the same care as wine. Expect a calm room where details matter—glassware, lighting, and the small courtesies that make a night flow.'
    },
    {
        'name': 'Paste Bangkok',
        'description_full': 'Heirloom Thai flavors rendered with clarity and balance. Curries and relishes are layered and meticulously sourced. Flavors chase balance rather than blunt heat, layering herbs, citrus, and a measured sweetness over clean textures. Dishes land quickly from a focused kitchen, and staff help dial spice levels so first‑timers feel welcome. Portions are built for sharing, which makes it easy to sample across salads, grills, and a curry or two. Regulars know to mix a crunchy snack with one soup for contrast, then finish with something charcoal‑kissed.'
    },
    {
        'name': 'Saneh Jaan',
        'description_full': 'Polished Thai cooking rooted in royal traditions and seasonal produce. Service is gracious and measured. Flavors chase balance rather than blunt heat, layering herbs, citrus, and a measured sweetness over clean textures. Dishes land quickly from a focused kitchen, and staff help dial spice levels so first‑timers feel welcome. Portions are built for sharing, which makes it easy to sample across salads, grills, and a curry or two. Regulars know to mix a crunchy snack with one soup for contrast, then finish with something charcoal‑kissed.'
    },
    {
        'name': 'Khao Ekkamai',
        'description_full': 'Refined Thai cuisine under Chef Ian Kittichai with thoughtful curries and relishes. The dining room is quietly luxurious. Menus evolve with the market, so courses feel anchored in the season rather than locked to a script. Service keeps the pacing unhurried and conversational, giving room for stories about sourcing and technique. Pairings are thoughtful without being fussy, and non‑alcoholic options are treated with the same care as wine. Expect a calm room where details matter—glassware, lighting, and the small courtesies that make a night flow.'
    },
    {
        'name': 'The Local by Oamthong Thai Cuisine',
        'description_full': 'Teak-house Thai showcasing family recipes and central-region flavors. It doubles as a living museum of ingredients. Flavors chase balance rather than blunt heat, layering herbs, citrus, and a measured sweetness over clean textures. Dishes land quickly from a focused kitchen, and staff help dial spice levels so first‑timers feel welcome. Portions are built for sharing, which makes it easy to sample across salads, grills, and a curry or two. Regulars know to mix a crunchy snack with one soup for contrast, then finish with something charcoal‑kissed.'
    },
    {
        'name': 'Appia',
        'description_full': 'Roman-leaning trattoria energy—porchetta, handmade pasta, and soulful sides. The wine list reads like a friendly guide through Italy. The room leans warm—wood, soft light, and the steady clink of stemware that signals an easy night ahead. Pasta sauces shine through reduction and restraint, and the grill sends out quiet smoke and honest char. Staff speak the menu fluently and nudge you toward seasonal picks without the hard sell. It\'s a place to linger; get bread, share a salad, then split a main and keep a little space for dessert.'
    }
]

def step1_insert_places():
    """Этап 1: Вставка мест в БД"""
    logger.info("📥 ЭТАП 1: Вставка мест в БД")
    
    db = SessionLocal()
    inserted_count = 0
    
    try:
        for place_data in test_places:
            # Проверяем, не существует ли уже
            existing = db.query(Place).filter(Place.name == place_data['name']).first()
            if existing:
                logger.info(f"⚠️  Место уже существует: {place_data['name']}")
                continue
            
            # Создаем новое место
            place = Place(
                name=place_data['name'],
                description_full=place_data['description_full'],
                source='manual_test',
                source_url=f"manual_test_{place_data['name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                scraped_at=datetime.now(),
                processing_status='new'
            )
            
            db.add(place)
            inserted_count += 1
            logger.info(f"✅ Добавлено: {place_data['name']}")
        
        db.commit()
        logger.info(f"🎉 ЭТАП 1 ЗАВЕРШЕН: Добавлено {inserted_count} новых мест")
        
    except Exception as e:
        logger.error(f"❌ Ошибка вставки: {e}")
        db.rollback()
    finally:
        db.close()

def step2_show_places():
    """Этап 2: Показ мест для саммаризации"""
    logger.info("📋 ЭТАП 2: Места готовые к саммаризации")
    
    db = SessionLocal()
    try:
        places = db.query(Place).filter(
            Place.processing_status == 'new',
            Place.source == 'manual_test'
        ).all()
        
        logger.info(f"Найдено {len(places)} мест для саммаризации:")
        for i, place in enumerate(places, 1):
            logger.info(f"{i}. {place.name}")
            logger.info(f"   Описание: {place.description_full[:100]}...")
            logger.info(f"   Статус: {place.processing_status}")
            logger.info("")
        
    finally:
        db.close()

def step3_show_places_for_google():
    """Этап 3: Показ мест для обогащения Google API"""
    logger.info("🌍 ЭТАП 3: Места готовые к обогащению Google API")
    
    db = SessionLocal()
    try:
        places = db.query(Place).filter(
            Place.processing_status == 'summarized',
            Place.source == 'manual_test'
        ).all()
        
        logger.info(f"Найдено {len(places)} мест для обогащения Google API:")
        for i, place in enumerate(places, 1):
            logger.info(f"{i}. {place.name}")
            logger.info(f"   Саммари: {place.summary[:100] if place.summary else 'Нет'}...")
            logger.info(f"   Теги: {place.tags_csv}")
            logger.info(f"   Статус: {place.processing_status}")
            logger.info("")
        
    finally:
        db.close()

def step4_show_places_for_ai_editor():
    """Этап 4: Показ мест для AI Editor проверки"""
    logger.info("🎯 ЭТАП 4: Места готовые к AI Editor проверке")
    
    db = SessionLocal()
    try:
        places = db.query(Place).filter(
            Place.processing_status == 'published',
            Place.source == 'manual_test'
        ).all()
        
        logger.info(f"Найдено {len(places)} мест для AI Editor проверки:")
        for i, place in enumerate(places, 1):
            logger.info(f"{i}. {place.name}")
            logger.info(f"   Google Place ID: {place.gmaps_place_id}")
            logger.info(f"   Фотография: {place.picture_url[:50] if place.picture_url else 'Нет'}...")
            logger.info(f"   Статус: {place.processing_status}")
            logger.info("")
        
    finally:
        db.close()

def main():
    """Главная функция"""
    logger.info("🚀 РУЧНАЯ ОБРАБОТКА МЕСТ ПОЭТАПНО")
    logger.info("="*50)
    
    # Этап 1: Вставка мест
    step1_insert_places()
    
    print("\n" + "="*50)
    input("Нажмите Enter для перехода к этапу 2...")
    
    # Этап 2: Показ мест для саммаризации
    step2_show_places()
    
    print("\n" + "="*50)
    input("Нажмите Enter для перехода к этапу 3...")
    
    # Этап 3: Показ мест для Google API
    step3_show_places_for_google()
    
    print("\n" + "="*50)
    input("Нажмите Enter для перехода к этапу 4...")
    
    # Этап 4: Показ мест для AI Editor
    step4_show_places_for_ai_editor()
    
    logger.info("🎉 Все этапы показаны!")

if __name__ == "__main__":
    main()
