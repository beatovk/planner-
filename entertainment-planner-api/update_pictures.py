#!/usr/bin/env python3
"""
Скрипт для обновления картинок мест без picture_url
"""
import requests
from bs4 import BeautifulSoup
import sqlite3
import time
from urllib.parse import urljoin
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_image_url(soup, base_url="https://www.timeout.com"):
    """Извлечение URL изображения"""
    # 1. Пробуем meta og:image (самый надежный)
    og_image = soup.find('meta', {'property': 'og:image'})
    if og_image and og_image.get('content'):
        return og_image['content']
    
    # 2. Ищем первое крупное изображение в контенте
    hero_images = soup.select('h1 + * img, .hero img, .featured img')
    for img in hero_images:
        src = img.get('src') or img.get('data-src')
        if src:
            return urljoin(base_url, src)
    
    # 3. Fallback: первое изображение в статье
    article_img = soup.select_one('article img, main img')
    if article_img:
        src = article_img.get('src') or article_img.get('data-src')
        if src:
            return urljoin(base_url, src)
    
    return None

def update_pictures():
    """Обновить картинки для мест без picture_url"""
    conn = sqlite3.connect('entertainment.db')
    cursor = conn.cursor()
    
    # Получаем места без картинок
    cursor.execute("""
        SELECT id, name, source_url 
        FROM places 
        WHERE processing_status = 'summarized' 
        AND (picture_url IS NULL OR picture_url = '')
        AND source_url LIKE '%timeout.com%'
        LIMIT 50
    """)
    
    places = cursor.fetchall()
    logger.info(f"Найдено {len(places)} мест без картинок")
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    })
    
    updated = 0
    for place_id, name, source_url in places:
        try:
            logger.info(f"Обрабатываем: {name}")
            
            # Делаем запрос к странице
            time.sleep(1)  # Вежливый rate limit
            response = session.get(source_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Извлекаем картинку
            image_url = extract_image_url(soup)
            
            if image_url:
                # Обновляем в базе
                cursor.execute("""
                    UPDATE places 
                    SET picture_url = ? 
                    WHERE id = ?
                """, (image_url, place_id))
                
                logger.info(f"✅ Обновлено: {name} -> {image_url}")
                updated += 1
            else:
                logger.warning(f"❌ Картинка не найдена: {name}")
                
        except Exception as e:
            logger.error(f"Ошибка для {name}: {e}")
    
    conn.commit()
    conn.close()
    
    logger.info(f"Обновлено {updated} мест")

if __name__ == "__main__":
    update_pictures()
