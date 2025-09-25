#!/usr/bin/env python3
"""
Отладка структуры TimeOut страниц
"""

import requests
from bs4 import BeautifulSoup
import time

def debug_page_structure(url):
    print(f"\n🔍 Анализируем: {url}")
    print("=" * 80)
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Ищем различные селекторы для мест
        selectors_to_try = [
            'h3 a[href*="/bangkok/restaurants/"]',
            'h2 a[href*="/bangkok/restaurants/"]',
            'h1 a[href*="/bangkok/restaurants/"]',
            'a[href*="/bangkok/restaurants/"]',
            '.listing-item a[href*="/bangkok/restaurants/"]',
            '.place-item a[href*="/bangkok/restaurants/"]',
            '.venue-item a[href*="/bangkok/restaurants/"]',
            'article a[href*="/bangkok/restaurants/"]',
            '.card a[href*="/bangkok/restaurants/"]',
            '.item a[href*="/bangkok/restaurants/"]'
        ]
        
        print("🔍 Поиск ссылок на рестораны:")
        for selector in selectors_to_try:
            links = soup.select(selector)
            print(f"  {selector}: {len(links)} ссылок")
            if links:
                for i, link in enumerate(links[:3]):  # Показываем первые 3
                    print(f"    {i+1}. {link.get_text().strip()[:50]} -> {link.get('href')}")
        
        # Ищем заголовки статей
        print("\n📰 Заголовки статей:")
        article_titles = soup.find_all(['h1', 'h2', 'h3'], string=lambda text: text and 'restaurant' in text.lower())
        for i, title in enumerate(article_titles[:5]):
            print(f"  {i+1}. {title.get_text().strip()}")
        
        # Ищем списки мест
        print("\n📋 Списки мест:")
        list_items = soup.find_all(['li', 'div'], class_=lambda x: x and any(word in x.lower() for word in ['place', 'venue', 'restaurant', 'cafe', 'item', 'listing']))
        print(f"  Найдено элементов списка: {len(list_items)}")
        
        # Ищем контейнеры с местами
        print("\n🏢 Контейнеры с местами:")
        containers = soup.find_all(['div', 'section', 'article'], class_=lambda x: x and any(word in x.lower() for word in ['list', 'places', 'venues', 'restaurants', 'cafes', 'items']))
        for i, container in enumerate(containers[:3]):
            print(f"  {i+1}. {container.get('class')} - {len(container.find_all('a'))} ссылок")
        
        # Сохраняем HTML для анализа
        with open(f'debug_{url.split("/")[-1]}.html', 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        print(f"\n💾 HTML сохранен в debug_{url.split('/')[-1]}.html")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    test_urls = [
        'https://www.timeout.com/bangkok/restaurants/best-restaurants-and-cafes-asoke',
        'https://www.timeout.com/bangkok/restaurants/best-places-to-eat-iconsiam',
        'https://www.timeout.com/bangkok/news/thailand-leads-asias-50-best-restaurants-2025-032625'
    ]
    
    for url in test_urls:
        debug_page_structure(url)
        time.sleep(2)  # Пауза между запросами
