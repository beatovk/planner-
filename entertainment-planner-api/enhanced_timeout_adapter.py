#!/usr/bin/env python3
"""
Улучшенный адаптер для парсинга TimeOut Bangkok
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import time
from typing import List, Dict, Any

class EnhancedTimeOutAdapter:
    def __init__(self):
        self.base_url = "https://www.timeout.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def parse_list_page(self, url: str) -> List[Dict[str, Any]]:
        """Парсинг страницы со списком мест"""
        print(f"🔍 Парсинг: {url}")
        
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            places = []
            
            # Метод 1: Поиск по заголовкам с номерами
            places.extend(self._extract_numbered_places(soup))
            
            # Метод 2: Поиск в контейнерах списков
            places.extend(self._extract_from_containers(soup))
            
            # Метод 3: Поиск по ссылкам на рестораны
            places.extend(self._extract_restaurant_links(soup))
            
            # Метод 4: Поиск по JSON-LD структурам
            places.extend(self._extract_from_json_ld(soup))
            
            # Удаляем дубликаты
            places = self._remove_duplicates(places)
            
            print(f"  ✅ Найдено мест: {len(places)}")
            return places
            
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
            return []
    
    def _extract_numbered_places(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Поиск мест с номерами (1., 2., 3. и т.д.)"""
        places = []
        
        # Ищем заголовки с номерами
        numbered_patterns = [
            r'^\d+\.\s+(.+)',  # 1. Название
            r'^\d+\s+(.+)',    # 1 Название
            r'^\(\d+\)\s+(.+)' # (1) Название
        ]
        
        for pattern in numbered_patterns:
            headers = soup.find_all(['h1', 'h2', 'h3', 'h4'], string=re.compile(pattern))
            for header in headers:
                text = header.get_text().strip()
                match = re.match(pattern, text)
                if match:
                    name = match.group(1).strip()
                    if self._is_valid_place_name(name):
                        place = {
                            'title': name,
                            'detail_url': self._find_place_url(header),
                            'teaser': None,
                            'address_fallback': None,
                            'hours_fallback': None,
                            'number': self._extract_number(text)
                        }
                        places.append(place)
        
        return places
    
    def _extract_from_containers(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Поиск мест в контейнерах списков"""
        places = []
        
        # Ищем контейнеры с местами
        container_selectors = [
            '._listContainer_130k9_1',
            '._container_1k2b4_1',
            '._popularPlaces_1pnw6_1',
            '[class*="list"]',
            '[class*="grid"]',
            '[class*="container"]'
        ]
        
        for selector in container_selectors:
            containers = soup.select(selector)
            for container in containers:
                # Ищем заголовки внутри контейнера
                headers = container.find_all(['h1', 'h2', 'h3', 'h4', 'h5'])
                for header in headers:
                    text = header.get_text().strip()
                    if self._is_valid_place_name(text) and len(text) > 3:
                        place = {
                            'title': text,
                            'detail_url': self._find_place_url(header),
                            'teaser': None,
                            'address_fallback': None,
                            'hours_fallback': None,
                            'number': len(places) + 1
                        }
                        places.append(place)
        
        return places
    
    def _extract_restaurant_links(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Поиск ссылок на рестораны"""
        places = []
        
        # Ищем все ссылки на рестораны
        links = soup.find_all('a', href=re.compile(r'/bangkok/restaurants/'))
        
        for link in links:
            href = link.get('href')
            text = link.get_text().strip()
            
            # Пропускаем социальные сети и служебные ссылки
            if any(social in href.lower() for social in ['facebook', 'twitter', 'pinterest', 'share', 'getyourguide']):
                continue
            
            if self._is_valid_place_name(text) and len(text) > 3:
                full_url = href if href.startswith('http') else self.base_url + href
                place = {
                    'title': text,
                    'detail_url': full_url,
                    'teaser': None,
                    'address_fallback': None,
                    'hours_fallback': None,
                    'number': len(places) + 1
                }
                places.append(place)
        
        return places
    
    def _extract_from_json_ld(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Поиск мест в JSON-LD структурах"""
        places = []
        
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and 'itemListElement' in data:
                    for item in data['itemListElement']:
                        if 'name' in item:
                            name = item['name']
                            if self._is_valid_place_name(name):
                                place = {
                                    'title': name,
                                    'detail_url': item.get('url', ''),
                                    'teaser': None,
                                    'address_fallback': None,
                                    'hours_fallback': None,
                                    'number': len(places) + 1
                                }
                                places.append(place)
            except (json.JSONDecodeError, KeyError):
                continue
        
        return places
    
    def _is_valid_place_name(self, name: str) -> bool:
        """Проверка, является ли строка валидным названием места"""
        if not name or len(name) < 3:
            return False
        
        # Исключаем служебные тексты
        excluded = [
            'read more', 'photograph:', 'time out', 'bangkok', 'restaurants',
            'cafes', 'best', 'top', 'guide', 'list', 'share', 'facebook',
            'twitter', 'pinterest', 'instagram', 'youtube', 'tiktok',
            'email', 'whatsapp', 'read review', 'photo:', 'jason lang',
            'sereechai puttes', 'nuti pramoch', 'casual eateries',
            'bakeries to find perfect sourdough bread',
            '5 bakeries to find perfect sourdough bread',
            'freeform expressions of neo-indian cuisine',
            'the dk experience', 'review: what to expect from the shake shack x potong collab'
        ]
        
        name_lower = name.lower().strip()
        if any(excluded_word in name_lower for excluded_word in excluded):
            return False
        
        # Исключаем очень короткие или длинные названия
        if len(name) < 3 or len(name) > 100:
            return False
        
        # Исключаем названия, состоящие только из цифр и символов
        if re.match(r'^[\d\s\.\-_]+$', name):
            return False
        
        return True
    
    def _find_place_url(self, element) -> str:
        """Поиск URL места в элементе"""
        # Ищем ссылку в самом элементе
        link = element.find('a')
        if link and link.get('href'):
            href = link.get('href')
            return href if href.startswith('http') else self.base_url + href
        
        # Ищем ссылку в родительском элементе
        parent = element.parent
        if parent:
            link = parent.find('a')
            if link and link.get('href'):
                href = link.get('href')
                return href if href.startswith('http') else self.base_url + href
        
        return ""
    
    def _extract_number(self, text: str) -> int:
        """Извлечение номера из текста"""
        match = re.search(r'(\d+)', text)
        return int(match.group(1)) if match else 0
    
    def _remove_duplicates(self, places: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Удаление дубликатов по названию"""
        seen = set()
        unique_places = []
        
        for place in places:
            name_key = place['title'].lower().strip()
            if name_key not in seen:
                seen.add(name_key)
                unique_places.append(place)
        
        return unique_places

# Тестирование
if __name__ == "__main__":
    adapter = EnhancedTimeOutAdapter()
    
    test_urls = [
        'https://www.timeout.com/bangkok/restaurants/best-restaurants-and-cafes-asoke',
        'https://www.timeout.com/bangkok/restaurants/best-places-to-eat-iconsiam',
        'https://www.timeout.com/bangkok/restaurants/bangkoks-best-new-cafes-of-2025'
    ]
    
    for url in test_urls:
        places = adapter.parse_list_page(url)
        print(f"\n📊 Результаты для {url}:")
        for i, place in enumerate(places[:5], 1):
            print(f"  {i}. {place['title']} -> {place['detail_url']}")
        print(f"  ... и еще {len(places) - 5} мест" if len(places) > 5 else "")
