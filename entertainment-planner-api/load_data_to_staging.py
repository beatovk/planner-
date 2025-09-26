#!/usr/bin/env python3
"""Load data from local DB to staging places_search table"""

import json
from apps.core.db import engine
from sqlalchemy import text

def load_data():
    # Читаем экспортированные данные
    with open('places_export.json', 'r', encoding='utf-8') as f:
        places = json.load(f)

    print(f'Загружено {len(places)} записей из JSON')

    with engine.connect() as conn:
        # Очищаем таблицу places_search
        conn.execute(text('DELETE FROM places_search'))
        print('✅ Таблица places_search очищена')
        
        # Вставляем все данные
        for i, place in enumerate(places):
            if i % 100 == 0:
                print(f'Обработано {i}/{len(places)} записей...')
            
            search_text = f"{place['name'] or ''} {place['tags_csv'] or ''} {place['summary'] or ''} {place['category'] or ''}"
            
            conn.execute(text('''
                INSERT INTO places_search (place_id, name, category, summary, tags_csv, lat, lng, picture_url, processing_status, search_text, created_at)
                VALUES (:place_id, :name, :category, :summary, :tags_csv, :lat, :lng, :picture_url, :processing_status, :search_text, CURRENT_TIMESTAMP)
            '''), {
                'place_id': place['id'],
                'name': place['name'],
                'category': place['category'],
                'summary': place['summary'],
                'tags_csv': place['tags_csv'],
                'lat': place['lat'],
                'lng': place['lng'],
                'picture_url': place['picture_url'],
                'processing_status': place['processing_status'],
                'search_text': search_text
            })
        
        conn.commit()
        print(f'✅ Загружено {len(places)} записей в places_search')

if __name__ == "__main__":
    load_data()
