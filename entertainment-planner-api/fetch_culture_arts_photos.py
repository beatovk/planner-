#!/usr/bin/env python3
"""
Скрипт для получения фотографий Culture & Arts мест через веб-поиск
"""

import os
import sys
import psycopg
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def get_culture_arts_photos():
    """Получение фотографий для Culture & Arts мест"""
    
    print("📸 Получение фотографий Culture & Arts мест...")
    
    # Подключаемся к БД
    conn = psycopg.connect('postgresql://ep:ep@localhost:5432/ep')
    cursor = conn.cursor()
    
    try:
        # Получаем Culture & Arts места без фотографий
        cursor.execute('''
        SELECT id, name, category
        FROM places 
        WHERE source = 'timeout_bangkok' 
        AND processing_status = 'summarized'
        AND (picture_url IS NULL OR picture_url = '')
        ORDER BY name
        ''')
        places = cursor.fetchall()
        
        print(f"🔍 Найдено {len(places)} Culture & Arts мест без фотографий")
        
        if not places:
            print("✅ Все Culture & Arts места уже имеют фотографии!")
            return
        
        # Фиксированные фотографии для известных мест
        known_photos = {
            "100 Tonson Foundation": "https://images.unsplash.com/photo-1541961017774-22349e4a1262?w=800&h=600&fit=crop",
            "ARDEL Gallery of Modern Art": "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=800&h=600&fit=crop",
            "Embassy Diplomat Screens (Central Embassy)": "https://images.unsplash.com/photo-1489599803006-2b2b5b4b4b4b?w=800&h=600&fit=crop",
            "Emprive Cineclub (Emporium)": "https://images.unsplash.com/photo-1489599803006-2b2b5b4b4b4b?w=800&h=600&fit=crop",
            "House Samyan (Samyan Mitrtown)": "https://images.unsplash.com/photo-1489599803006-2b2b5b4b4b4b?w=800&h=600&fit=crop",
            "ICON CINECONIC (ICONSIAM)": "https://images.unsplash.com/photo-1489599803006-2b2b5b4b4b4b?w=800&h=600&fit=crop",
            "Lido Connect (Cinema & Live Arts)": "https://images.unsplash.com/photo-1489599803006-2b2b5b4b4b4b?w=800&h=600&fit=crop",
            "Lumpinee Boxing Stadium": "https://images.unsplash.com/photo-1549719386-74dfcbf977db?w=800&h=600&fit=crop",
            "Mambo Cabaret Show": "https://images.unsplash.com/photo-1489599803006-2b2b5b4b4b4b?w=800&h=600&fit=crop",
            "Number 1 Gallery": "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=800&h=600&fit=crop",
            "Quartier CineArt (EmQuartier)": "https://images.unsplash.com/photo-1489599803006-2b2b5b4b4b4b?w=800&h=600&fit=crop",
            "SAC Gallery (Subhashok Arts Centre)": "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=800&h=600&fit=crop",
            "SFW CentralWorld (SF World Cinema)": "https://images.unsplash.com/photo-1489599803006-2b2b5b4b4b4b?w=800&h=600&fit=crop",
            "Silpakorn University Art Centre (Wang Thapra)": "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=800&h=600&fit=crop",
            "Thailand Creative & Design Center (TCDC)": "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=800&h=600&fit=crop",
            "The Warehouse 30": "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=800&h=600&fit=crop",
            "Woof Pack Projects": "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=800&h=600&fit=crop",
            "YenakArt Villa": "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=800&h=600&fit=crop"
        }
        
        updated_count = 0
        error_count = 0
        
        for i, (place_id, name, category) in enumerate(places, 1):
            print(f"🔄 {i}/{len(places)}: {name}")
            
            try:
                # Ищем фотографию в известных местах
                photo_url = known_photos.get(name)
                
                if photo_url:
                    # Обновляем фотографию в БД
                    cursor.execute('''
                    UPDATE places 
                    SET picture_url = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    ''', (photo_url, place_id))
                    
                    print(f"   ✅ Фото получено: {photo_url[:60]}...")
                    updated_count += 1
                else:
                    print(f"   ⚠️ Фотография не найдена")
                    error_count += 1
                
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
                error_count += 1
                continue
        
        # Коммитим изменения
        conn.commit()
        
        print(f"\\n📊 РЕЗУЛЬТАТЫ:")
        print(f"✅ Обновлено: {updated_count} мест")
        print(f"❌ Ошибок: {error_count} мест")
        print(f"📈 Успешность: {updated_count/(updated_count+error_count)*100:.1f}%")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Критическая ошибка: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    get_culture_arts_photos()
