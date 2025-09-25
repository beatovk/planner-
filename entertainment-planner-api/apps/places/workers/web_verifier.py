#!/usr/bin/env python3
"""
Web Verifier - модуль для веб-поиска и проверки достоверности данных
"""

import requests
import json
import logging
import time
import random
from typing import List, Dict, Optional, Tuple, Any
from urllib.parse import quote_plus
import re

logger = logging.getLogger(__name__)


class WebVerifier:
    """
    Класс для веб-поиска и проверки достоверности данных
    """
    
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
        
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def verify_place_data(self, place_name: str, place_category: str, place_address: str = None) -> Dict[str, Any]:
        """
        Проверяет достоверность данных места через веб-поиск
        """
        try:
            # Формируем поисковые запросы
            search_queries = self._generate_search_queries(place_name, place_category, place_address)
            
            verification_results = []
            
            # Проверяем каждый запрос (максимум 2-3 источника)
            for i, query in enumerate(search_queries[:3]):
                try:
                    result = self._search_place_info(query, place_name)
                    if result:
                        verification_results.append(result)
                    
                    # Небольшая задержка между запросами
                    time.sleep(random.uniform(1, 2))
                    
                except Exception as e:
                    logger.warning(f"Ошибка поиска для запроса '{query}': {e}")
                    continue
            
            # Анализируем результаты
            return self._analyze_verification_results(verification_results, place_name, place_category)
            
        except Exception as e:
            logger.error(f"Ошибка верификации места {place_name}: {e}")
            return {
                "verified": False,
                "confidence": 0.0,
                "sources": [],
                "issues": [f"Ошибка верификации: {e}"],
                "suggestions": []
            }
    
    def _generate_search_queries(self, name: str, category: str, address: str = None) -> List[str]:
        """Генерирует поисковые запросы для проверки"""
        queries = []
        
        # Основной запрос с названием и категорией
        base_query = f'"{name}" {category} Bangkok'
        queries.append(base_query)
        
        # Запрос с адресом если есть
        if address:
            address_query = f'"{name}" "{address}" Bangkok'
            queries.append(address_query)
        
        # Запрос только по названию
        name_query = f'"{name}" restaurant bar Bangkok'
        queries.append(name_query)
        
        return queries
    
    def _search_place_info(self, query: str, place_name: str) -> Optional[Dict[str, Any]]:
        """Выполняет поиск информации о месте"""
        try:
            # Используем DuckDuckGo для поиска
            search_url = "https://duckduckgo.com/html/"
            params = {
                'q': query,
                'kl': 'en-us'
            }
            
            headers = {
                'User-Agent': random.choice(self.user_agents),
                'Referer': 'https://duckduckgo.com/'
            }
            
            response = self.session.get(search_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Парсим результаты поиска
            return self._parse_search_results(response.text, place_name)
            
        except Exception as e:
            logger.warning(f"Ошибка поиска для '{query}': {e}")
            return None
    
    def _parse_search_results(self, html: str, place_name: str) -> Optional[Dict[str, Any]]:
        """Парсит результаты поиска"""
        try:
            # Простой парсинг HTML (в реальной реализации можно использовать BeautifulSoup)
            # Ищем упоминания названия места
            name_mentions = len(re.findall(re.escape(place_name.lower()), html.lower()))
            
            # Ищем релевантные ключевые слова
            relevant_keywords = ['restaurant', 'bar', 'cafe', 'bangkok', 'thailand', 'food', 'dining']
            keyword_matches = sum(1 for keyword in relevant_keywords if keyword.lower() in html.lower())
            
            # Ищем ссылки на релевантные сайты
            relevant_domains = ['tripadvisor', 'google', 'foursquare', 'zomato', 'timeout', 'bk.asia-city']
            domain_matches = sum(1 for domain in relevant_domains if domain in html.lower())
            
            return {
                "name_mentions": name_mentions,
                "keyword_matches": keyword_matches,
                "domain_matches": domain_matches,
                "relevance_score": (name_mentions * 2 + keyword_matches + domain_matches) / 10
            }
            
        except Exception as e:
            logger.warning(f"Ошибка парсинга результатов: {e}")
            return None
    
    def _analyze_verification_results(self, results: List[Dict], place_name: str, place_category: str) -> Dict[str, Any]:
        """Анализирует результаты верификации"""
        if not results:
            return {
                "verified": False,
                "confidence": 0.0,
                "sources": [],
                "issues": ["Нет результатов поиска"],
                "suggestions": ["Проверить правильность написания названия"]
            }
        
        # Вычисляем общий score
        total_score = sum(r.get("relevance_score", 0) for r in results)
        avg_score = total_score / len(results)
        
        # Определяем уровень доверия
        if avg_score >= 0.7:
            confidence = "high"
            verified = True
        elif avg_score >= 0.4:
            confidence = "medium"
            verified = True
        else:
            confidence = "low"
            verified = False
        
        # Формируем список проблем
        issues = []
        suggestions = []
        
        if avg_score < 0.3:
            issues.append("Низкая релевантность в поисковых результатах")
            suggestions.append("Проверить правильность названия и категории")
        
        if not any(r.get("domain_matches", 0) > 0 for r in results):
            issues.append("Нет упоминаний на авторитетных сайтах")
            suggestions.append("Проверить существование места")
        
        return {
            "verified": verified,
            "confidence": avg_score,
            "sources": len(results),
            "issues": issues,
            "suggestions": suggestions,
            "details": results
        }
    
    def search_quality_images(self, place_name: str, place_category: str) -> List[str]:
        """
        Ищет качественные изображения места
        """
        try:
            # Формируем поисковый запрос для изображений
            image_query = f"{place_name} {place_category} Bangkok professional photo"
            
            # Используем DuckDuckGo для поиска изображений
            search_url = "https://duckduckgo.com/"
            params = {
                'q': image_query,
                'iax': 'images',
                'ia': 'images'
            }
            
            headers = {
                'User-Agent': random.choice(self.user_agents),
                'Referer': 'https://duckduckgo.com/'
            }
            
            response = self.session.get(search_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Парсим результаты поиска изображений
            return self._parse_image_results(response.text)
            
        except Exception as e:
            logger.warning(f"Ошибка поиска изображений для '{place_name}': {e}")
            return []
    
    def _parse_image_results(self, html: str) -> List[str]:
        """Парсит результаты поиска изображений"""
        try:
            # Простой парсинг для извлечения URL изображений
            # В реальной реализации можно использовать более сложный парсинг
            image_urls = []
            
            # Ищем URL изображений в HTML
            img_pattern = r'https://[^"\s]+\.(?:jpg|jpeg|png|webp)(?:\?[^"\s]*)?'
            matches = re.findall(img_pattern, html, re.IGNORECASE)
            
            # Фильтруем качественные изображения
            for url in matches[:10]:  # Берем первые 10
                if self._is_quality_image_url(url):
                    image_urls.append(url)
            
            return image_urls[:5]  # Возвращаем максимум 5 лучших
            
        except Exception as e:
            logger.warning(f"Ошибка парсинга изображений: {e}")
            return []
    
    def _is_quality_image_url(self, url: str) -> bool:
        """Проверяет качество изображения по URL"""
        try:
            # Проверяем расширение
            quality_extensions = ['.jpg', '.jpeg', '.png', '.webp']
            if not any(url.lower().endswith(ext) for ext in quality_extensions):
                return False
            
            # Исключаем маленькие изображения (по параметрам URL)
            if any(param in url.lower() for param in ['thumb', 'small', 'icon', 'avatar']):
                return False
            
            # Предпочитаем изображения с указанием размера
            if any(param in url.lower() for param in ['w=', 'width=', 'h=', 'height=']):
                return True
            
            # Исключаем социальные сети и аватары
            if any(domain in url.lower() for domain in ['facebook', 'instagram', 'twitter', 'avatar']):
                return False
            
            return True
            
        except Exception:
            return False


def main():
    """Тестирование WebVerifier"""
    verifier = WebVerifier()
    
    # Тестовые данные
    test_place = {
        "name": "Sirocco Sky Bar",
        "category": "Bar",
        "address": "Lebua at State Tower, Bangkok"
    }
    
    print("🔍 Тестирование WebVerifier...")
    
    # Проверяем достоверность
    verification = verifier.verify_place_data(
        test_place["name"],
        test_place["category"],
        test_place["address"]
    )
    
    print(f"Результат верификации: {verification}")
    
    # Ищем изображения
    images = verifier.search_quality_images(
        test_place["name"],
        test_place["category"]
    )
    
    print(f"Найдено изображений: {len(images)}")
    for i, img in enumerate(images[:3], 1):
        print(f"  {i}. {img}")


if __name__ == "__main__":
    main()
