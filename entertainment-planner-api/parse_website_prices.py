#!/usr/bin/env python3
"""
Парсинг цен с сайтов заведений через websiteUri из Google Places API.
Ищем schema.org priceRange, меню с ценами в ฿, и другие ценовые паттерны.
"""

import re
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import json
from typing import Optional, Dict, Any
import time
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebsitePriceParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def parse_price_from_website(self, website_url: str) -> Optional[int]:
        """
        Парсит цену с сайта заведения.
        Возвращает price_level (0-4) или None если не найдено.
        """
        if not website_url:
            return None
            
        try:
            logger.info(f"Парсинг сайта: {website_url}")
            response = self.session.get(website_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 1. Ищем schema.org priceRange
            price_range = self._extract_schema_price_range(soup)
            if price_range:
                return self._map_price_range_to_level(price_range)
            
            # 2. Ищем цены в тексте (฿, baht, บาท)
            text_prices = self._extract_text_prices(soup.get_text())
            if text_prices:
                return self._map_prices_to_level(text_prices)
            
            # 3. Ищем в меню/price списках
            menu_prices = self._extract_menu_prices(soup)
            if menu_prices:
                return self._map_prices_to_level(menu_prices)
                
        except Exception as e:
            logger.warning(f"Ошибка парсинга {website_url}: {e}")
            
        return None
    
    def _extract_schema_price_range(self, soup: BeautifulSoup) -> Optional[str]:
        """Ищет schema.org priceRange в JSON-LD или microdata."""
        
        # JSON-LD
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    price_range = data.get('priceRange') or data.get('offers', {}).get('priceRange')
                    if price_range:
                        return str(price_range)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            price_range = item.get('priceRange') or item.get('offers', {}).get('priceRange')
                            if price_range:
                                return str(price_range)
            except:
                continue
        
        # Microdata
        for elem in soup.find_all(attrs={'itemprop': 'priceRange'}):
            return elem.get_text(strip=True)
            
        return None
    
    def _extract_text_prices(self, text: str) -> list:
        """Ищет цены в тексте (฿, baht, บาท)."""
        prices = []
        
        # Паттерны для тайских бат
        patterns = [
            r'฿\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # ฿1,000
            r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*฿',  # 1,000฿
            r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*baht',  # 1000 baht
            r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*บาท',  # 1000 บาท
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    # Убираем запятые и конвертируем в число
                    price = float(match.replace(',', ''))
                    if 50 <= price <= 10000:  # Разумный диапазон для ресторанов
                        prices.append(price)
                except:
                    continue
                    
        return prices
    
    def _extract_menu_prices(self, soup: BeautifulSoup) -> list:
        """Ищет цены в меню (div с price, menu-item и т.п.)."""
        prices = []
        
        # Селекторы для меню
        menu_selectors = [
            '.price', '.menu-price', '.item-price',
            '.menu-item', '.food-item', '.dish',
            '[class*="price"]', '[class*="menu"]'
        ]
        
        for selector in menu_selectors:
            for elem in soup.select(selector):
                text = elem.get_text()
                text_prices = self._extract_text_prices(text)
                prices.extend(text_prices)
                
        return prices
    
    def _map_price_range_to_level(self, price_range: str) -> Optional[int]:
        """Маппит priceRange строку в price_level (0-4)."""
        price_range = price_range.lower()
        
        # Обработка диапазонов типа "$10-20", "฿500-1000"
        if '-' in price_range or 'to' in price_range:
            # Берем среднее значение
            numbers = re.findall(r'[\d,]+', price_range)
            if len(numbers) >= 2:
                try:
                    low = float(numbers[0].replace(',', ''))
                    high = float(numbers[1].replace(',', ''))
                    avg_price = (low + high) / 2
                    return self._map_price_to_level(avg_price)
                except:
                    pass
        
        # Обработка "under $20", "over $50"
        if 'under' in price_range or 'below' in price_range:
            numbers = re.findall(r'[\d,]+', price_range)
            if numbers:
                try:
                    price = float(numbers[0].replace(',', ''))
                    return self._map_price_to_level(price * 0.7)  # Немного ниже
                except:
                    pass
                    
        if 'over' in price_range or 'above' in price_range:
            numbers = re.findall(r'[\d,]+', price_range)
            if numbers:
                try:
                    price = float(numbers[0].replace(',', ''))
                    return self._map_price_to_level(price * 1.3)  # Немного выше
                except:
                    pass
        
        # Обработка отдельных чисел
        numbers = re.findall(r'[\d,]+', price_range)
        if numbers:
            try:
                price = float(numbers[0].replace(',', ''))
                return self._map_price_to_level(price)
            except:
                pass
                
        return None
    
    def _map_prices_to_level(self, prices: list) -> Optional[int]:
        """Маппит список цен в price_level (0-4)."""
        if not prices:
            return None
            
        # Берем медианную цену
        prices.sort()
        median_price = prices[len(prices) // 2]
        return self._map_price_to_level(median_price)
    
    def _map_price_to_level(self, price: float) -> int:
        """Маппит цену в батах в price_level (0-4)."""
        # Адаптировано для тайских бат
        if price <= 0:
            return 0  # FREE
        elif price <= 150:
            return 1  # INEXPENSIVE
        elif price <= 400:
            return 2  # MODERATE  
        elif price <= 800:
            return 3  # EXPENSIVE
        else:
            return 4  # VERY_EXPENSIVE


def test_ki_izakaya():
    """Тестируем на Ki Izakaya."""
    from apps.core.db import SessionLocal
    from apps.places.models import Place
    from apps.places.services.google_places import GooglePlaces
    
    db = SessionLocal()
    try:
        # Находим Ki Izakaya
        place = db.query(Place).filter(Place.name.ilike('%Ki Izakaya%')).first()
        if not place:
            print("Ki Izakaya не найден в базе")
            return
            
        print(f"Найдено место: {place.name} (ID: {place.id})")
        print(f"Google Place ID: {place.gmaps_place_id}")
        print(f"Текущий price_level: {place.price_level}")
        
        if not place.gmaps_place_id:
            print("Нет Google Place ID")
            return
            
        # Получаем websiteUri из Google Places API
        google_client = GooglePlaces()
        details = google_client.place_details(place.gmaps_place_id)
        
        website_uri = details.get('websiteUri')
        print(f"Website URI: {website_uri}")
        
        if not website_uri:
            print("Нет website URI")
            return
            
        # Парсим цену с сайта
        parser = WebsitePriceParser()
        new_price_level = parser.parse_price_from_website(website_uri)
        
        print(f"Найденный price_level: {new_price_level}")
        
        if new_price_level is not None:
            # Обновляем в базе
            place.price_level = new_price_level
            db.commit()
            print(f"✅ Обновлен price_level: {new_price_level}")
        else:
            print("❌ Цена не найдена на сайте")
            
    finally:
        db.close()


if __name__ == "__main__":
    test_ki_izakaya()
