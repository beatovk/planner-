#!/usr/bin/env python3
"""
Отладочный скрипт для анализа ссылок на TimeOut
"""
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

def debug_timeout_links():
    """Анализируем все ссылки на странице TimeOut"""
    
    url = "https://www.timeout.com/bangkok/restaurants/bangkoks-best-new-cafes-of-2025"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }
    
    print("🔍 Анализируем ссылки на TimeOut...")
    response = requests.get(url, headers=headers, timeout=30)
    soup = BeautifulSoup(response.content, 'lxml')
    
    # Очищаем HTML
    for script in soup(["script", "style", "noscript"]):
        script.decompose()
    
    # Ищем основной контент
    main_content = soup.find('main') or soup.find('article')
    if not main_content:
        print("❌ Не найден основной контент")
        return
    
    # Ищем все ссылки на рестораны/кафе
    restaurant_links = main_content.find_all('a', href=re.compile(r'/bangkok/restaurants/'))
    
    print(f"📝 Найдено ссылок на рестораны: {len(restaurant_links)}")
    print("\n" + "="*80)
    
    valid_links = []
    filtered_links = []
    
    for i, link in enumerate(restaurant_links, 1):
        title = link.get_text().strip()
        href = link.get('href', '')
        full_url = urljoin("https://www.timeout.com", href)
        
        # Проверяем фильтры
        is_social = any(social in href.lower() for social in ['facebook', 'twitter', 'pinterest', 'whatsapp', 'mailto'])
        is_short = len(title) < 5
        is_service = title.lower() in ['read more', 'photograph:', 'javascript is not available', 'pin builder']
        
        status = "✅ ВАЛИДНАЯ"
        reason = ""
        
        if is_social:
            status = "❌ СОЦИАЛЬНАЯ СЕТЬ"
            reason = f"URL содержит: {[s for s in ['facebook', 'twitter', 'pinterest', 'whatsapp', 'mailto'] if s in href.lower()]}"
        elif is_short:
            status = "❌ КОРОТКОЕ НАЗВАНИЕ"
            reason = f"Длина: {len(title)} символов"
        elif is_service:
            status = "❌ СЛУЖЕБНЫЙ ТЕКСТ"
            reason = f"Текст: '{title}'"
        
        print(f"{i:2d}. {status}")
        print(f"    Название: '{title}'")
        print(f"    URL: {full_url}")
        if reason:
            print(f"    Причина фильтрации: {reason}")
        print()
        
        if status == "✅ ВАЛИДНАЯ":
            valid_links.append(link)
        else:
            filtered_links.append((link, reason))
    
    print("="*80)
    print(f"📊 ИТОГИ:")
    print(f"✅ Валидных ссылок: {len(valid_links)}")
    print(f"❌ Отфильтровано: {len(filtered_links)}")
    print(f"📝 Всего ссылок: {len(restaurant_links)}")
    
    if len(valid_links) < 28:
        print(f"\n⚠️  ПРОБЛЕМА: Найдено только {len(valid_links)} из 28 мест!")
        print("\n🔍 Анализируем отфильтрованные ссылки:")
        
        for link, reason in filtered_links:
            title = link.get_text().strip()
            href = link.get('href', '')
            print(f"- '{title}' -> {reason}")
    
    return valid_links, filtered_links

if __name__ == "__main__":
    debug_timeout_links()
