#!/usr/bin/env python3
"""
Скрипт для нормализации уровней цен в БД
Преобразует строковые форматы в числовые (0-4)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.core.db import SessionLocal
from apps.places.models import Place
from sqlalchemy import func

def normalize_price_level(price_level):
    """Нормализует уровень цен в числовой формат"""
    if price_level is None:
        return None
    
    # Если уже число, возвращаем как есть
    if isinstance(price_level, int):
        return price_level
    
    # Маппинг строковых значений
    mapping = {
        'PRICE_LEVEL_FREE': 0,
        'PRICE_LEVEL_INEXPENSIVE': 1,
        'PRICE_LEVEL_MODERATE': 2,
        'PRICE_LEVEL_EXPENSIVE': 3,
        'PRICE_LEVEL_VERY_EXPENSIVE': 4,
    }
    
    return mapping.get(price_level, None)

def fix_price_levels():
    """Исправляет уровни цен в БД"""
    db = SessionLocal()
    try:
        print("🔧 Начинаем нормализацию уровней цен...")
        
        # Получаем статистику до исправления
        price_stats_before = db.query(Place.price_level, func.count(Place.id)).group_by(Place.price_level).all()
        print(f"\\n📊 Статистика ДО исправления:")
        for price, count in price_stats_before:
            print(f"  {price}: {count} мест")
        
        # Получаем все места с нечисловыми уровнями цен
        places_to_fix = db.query(Place).filter(
            Place.price_level.isnot(None),
            Place.price_level.notlike('PRICE_LEVEL_%')
        ).all()
        
        print(f"\\n🔍 Найдено мест для исправления: {len(places_to_fix)}")
        
        # Исправляем каждое место
        fixed_count = 0
        for place in places_to_fix:
            old_price = place.price_level
            new_price = normalize_price_level(old_price)
            
            if new_price is not None and new_price != old_price:
                place.price_level = new_price
                print(f"  ID {place.id}: {old_price} → {new_price}")
                fixed_count += 1
        
        # Сохраняем изменения
        db.commit()
        print(f"\\n✅ Исправлено {fixed_count} мест")
        
        # Получаем статистику после исправления
        price_stats_after = db.query(Place.price_level, func.count(Place.id)).group_by(Place.price_level).all()
        print(f"\\n📊 Статистика ПОСЛЕ исправления:")
        for price, count in price_stats_after:
            print(f"  {price}: {count} мест")
        
        # Проверяем, что все уровни цен теперь числовые
        non_numeric = db.query(Place).filter(
            Place.price_level.isnot(None),
            Place.price_level.notlike('PRICE_LEVEL_%')
        ).count()
        
        if non_numeric == 0:
            print("\\n🎉 Все уровни цен успешно нормализованы!")
        else:
            print(f"\\n⚠️ Осталось {non_numeric} мест с нечисловыми уровнями цен")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_price_levels()
