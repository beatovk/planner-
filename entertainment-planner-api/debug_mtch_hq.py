#!/usr/bin/env python3
"""
Проверяем почему MTCH не входит в High Experience
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.core.db import get_db
from apps.places.models import Place
from sqlalchemy import text

def main():
    """Проверяем MTCH в базе данных"""
    print("ПРОВЕРКА MTCH В БАЗЕ ДАННЫХ")
    print("=" * 50)
    
    db = next(get_db())
    
    # Ищем все MTCH места
    mtch_places = db.query(Place).filter(Place.name.ilike('%mtch%')).all()
    
    print(f"Найдено MTCH мест: {len(mtch_places)}")
    print()
    
    for place in mtch_places:
        print(f"Место: {place.name}")
        print(f"  ID: {place.id}")
        print(f"  Статус: {place.processing_status}")
        print(f"  Координаты: {place.lat}, {place.lng}")
        print(f"  Теги: {place.tags_csv}")
        print(f"  Signals: {place.signals}")
        
        if place.signals:
            hq_experience = place.signals.get('hq_experience', False)
            quality_score = place.signals.get('quality_score', 0.0)
            local_gem = place.signals.get('local_gem', False)
            editor_pick = place.signals.get('editor_pick', False)
            extraordinary = place.signals.get('extraordinary', False)
            
            print(f"  hq_experience: {hq_experience}")
            print(f"  quality_score: {quality_score}")
            print(f"  local_gem: {local_gem}")
            print(f"  editor_pick: {editor_pick}")
            print(f"  extraordinary: {extraordinary}")
        
        print()
    
    # Проверяем материализованное представление
    print("ПРОВЕРКА МАТЕРИАЛИЗОВАННОГО ПРЕДСТАВЛЕНИЯ")
    print("=" * 50)
    
    try:
        result = db.execute(text("""
            SELECT name, tags_csv, signals 
            FROM epx.places_search_mv 
            WHERE name ILIKE '%mtch%'
        """)).fetchall()
        
        print(f"Найдено MTCH в MV: {len(result)}")
        for row in result:
            print(f"  {row[0]} - signals: {row[2]}")
    except Exception as e:
        print(f"Ошибка запроса MV: {e}")
    
    # Проверяем что считается High Experience
    print("\nПРОВЕРКА HIGH EXPERIENCE КРИТЕРИЕВ")
    print("=" * 50)
    
    try:
        result = db.execute(text("""
            SELECT name, signals->'hq_experience' as hq_exp, signals->'quality_score' as quality
            FROM places 
            WHERE name ILIKE '%matcha%' 
            AND processing_status IN ('summarized', 'published')
            ORDER BY (signals->'quality_score')::float DESC NULLS LAST
        """)).fetchall()
        
        print("Все matcha места по quality_score:")
        for row in result:
            print(f"  {row[0]} - hq_experience: {row[1]} - quality_score: {row[2]}")
    except Exception as e:
        print(f"Ошибка запроса: {e}")

if __name__ == "__main__":
    main()
