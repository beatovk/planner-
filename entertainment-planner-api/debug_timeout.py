#!/usr/bin/env python3
"""
Отладочный скрипт для анализа структуры страницы TimeOut
"""
import requests
from bs4 import BeautifulSoup
import re

def debug_timeout_page():
    """Анализируем структуру страницы TimeOut"""
    
    url = "https://www.timeout.com/bangkok/restaurants/bangkoks-best-new-cafes-of-2025"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }
    
    print("Загружаем страницу...")
    response = requests.get(url, headers=headers, timeout=30)
    print(f"Статус: {response.status_code}")
    
    soup = BeautifulSoup(response.content, 'lxml')
    
    print("\n=== АНАЛИЗ СТРУКТУРЫ СТРАНИЦЫ ===")
    
    # Ищем основной контент
    main_content = soup.find('main') or soup.find('article')
    print(f"Найден main/article: {main_content is not None}")
    
    if main_content:
        print(f"Тег main/article: {main_content.name}")
        print(f"Классы: {main_content.get('class', [])}")
    
    # Ищем заголовки
    print("\n=== ЗАГОЛОВКИ ===")
    for i in range(1, 7):
        headers = soup.find_all(f'h{i}')
        print(f"H{i}: {len(headers)} штук")
        
        for j, h in enumerate(headers[:3]):  # Показываем первые 3
            text = h.get_text().strip()
            if text and len(text) < 100:
                print(f"  {j+1}. {text}")
    
    # Ищем нумерованные пункты
    print("\n=== НУМЕРОВАННЫЕ ПУНКТЫ ===")
    
    # Ищем по разным паттернам
    patterns = [
        r'^\d+\.\s+',  # "1. Название"
        r'^\d+\.',     # "1."
        r'^\d+\s+',    # "1 Название"
    ]
    
    for pattern in patterns:
        print(f"\nПаттерн: {pattern}")
        elements = soup.find_all(string=re.compile(pattern))
        print(f"Найдено элементов: {len(elements)}")
        
        for i, elem in enumerate(elements[:5]):  # Показываем первые 5
            text = elem.strip()
            if text and len(text) < 100:
                print(f"  {i+1}. {text}")
    
    # Ищем ссылки
    print("\n=== ССЫЛКИ ===")
    links = soup.find_all('a', href=True)
    print(f"Всего ссылок: {len(links)}")
    
    # Ищем ссылки на рестораны/кафе
    restaurant_links = []
    for link in links:
        href = link.get('href', '')
        text = link.get_text().strip()
        
        if any(keyword in href.lower() for keyword in ['restaurant', 'cafe', 'bar', 'food']):
            restaurant_links.append((text, href))
    
    print(f"Ссылки на рестораны/кафе: {len(restaurant_links)}")
    for i, (text, href) in enumerate(restaurant_links[:5]):
        print(f"  {i+1}. {text} -> {href}")
    
    # Ищем контент статьи
    print("\n=== КОНТЕНТ СТАТЬИ ===")
    
    # Ищем div с классом article или content
    content_divs = soup.find_all('div', class_=re.compile(r'article|content|main', re.I))
    print(f"Div с классами article/content/main: {len(content_divs)}")
    
    for i, div in enumerate(content_divs[:2]):
        print(f"Div {i+1}: классы = {div.get('class', [])}")
        text_sample = div.get_text()[:200]
        print(f"Текст: {text_sample}...")
    
    # Сохраняем HTML для анализа
    with open('timeout_debug.html', 'w', encoding='utf-8') as f:
        f.write(soup.prettify())
    print(f"\nHTML сохранен в timeout_debug.html")

if __name__ == "__main__":
    debug_timeout_page()
