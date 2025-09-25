"""
BK Magazine парсер для сбора данных о местах
Следует спецификации MVP для парсинга BK Magazine
"""
import re
import time
import requests
from bs4 import BeautifulSoup, SoupStrainer
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin, urlparse
import logging

logger = logging.getLogger(__name__)


class BKMagazineAdapter:
    """Адаптер для парсинга BK Magazine"""
    
    def __init__(self, base_url: str = "https://bk.asia-city.com", rate_limit: float = 1.0):
        self.base_url = base_url
        self.rate_limit = rate_limit
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        })
    
    def _make_request(self, url: str) -> Optional[BeautifulSoup]:
        """Выполнить запрос с rate limiting"""
        try:
            time.sleep(self.rate_limit)  # Вежливый rate limit
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Очищаем HTML от технических элементов
            self._clean_html(soup)
            
            return soup
        except Exception as e:
            logger.error(f"Ошибка запроса {url}: {e}")
            return None
    
    def _clean_html(self, soup: BeautifulSoup):
        """Удаляет технические HTML элементы"""
        # Удаляем скрипты и стили
        for script in soup(["script", "style", "noscript"]):
            script.decompose()
        
        # Удаляем рекламные блоки
        for ad in soup.find_all(class_=re.compile(r'ad|advertisement|banner', re.I)):
            ad.decompose()
    
    def parse_article_page(self, article_url: str) -> List[Dict[str, Any]]:
        """Парсинг статьи BK Magazine для извлечения мест с креативным определением типа"""
        logger.info(f"Начинаем парсинг статьи: {article_url}")
        
        soup = self._make_request(article_url)
        if not soup:
            logger.error(f"Не удалось загрузить страницу: {article_url}")
            return []
        
        try:
            # Креативно определяем тип статьи
            article_type = self._detect_article_type(article_url, soup)
            logger.info(f"Определен тип статьи: {article_type}")
            
            # Применяем соответствующий метод извлечения
            places = self._extract_places(soup, article_type)
            
            # Удаляем дубликаты
            places = self._remove_duplicates(places)
            
            logger.info(f"Найдено {len(places)} мест в статье")
            
            # Показываем первые несколько мест
            for i, place in enumerate(places[:3], 1):
                logger.info(f"Место {i}: {place['title']}...")
            
            return places
            
        except Exception as e:
            logger.error(f"Ошибка парсинга статьи {article_url}: {e}")
            return []
    
    def _detect_article_type(self, url: str, soup: BeautifulSoup) -> str:
        """Креативно определяет тип статьи BK Magazine"""
        url_lower = url.lower()
        
        # Определяем по URL
        if 'restaurants' in url_lower:
            return 'restaurants'
        elif 'nightlife' in url_lower or 'bars' in url_lower:
            return 'nightlife'
        elif 'spa' in url_lower or 'health' in url_lower:
            return 'spa'
        elif 'breakfast' in url_lower:
            return 'breakfast'
        
        # Определяем по содержимому
        title = soup.find('title')
        if title:
            title_text = title.get_text().lower()
            if any(word in title_text for word in ['restaurant', 'dining', 'food', 'cuisine']):
                return 'restaurants'
            elif any(word in title_text for word in ['nightlife', 'bar', 'cocktail', 'club', 'pub']):
                return 'nightlife'
            elif any(word in title_text for word in ['spa', 'wellness', 'massage']):
                return 'spa'
        
        # Определяем по заголовкам h2
        h2_tags = soup.find_all('h2')
        restaurant_count = 0
        nightlife_count = 0
        
        for h2 in h2_tags[:10]:  # Проверяем первые 10 заголовков
            text = h2.get_text().lower()
            if any(word in text for word in ['bar', 'cocktail', 'pub', 'club', 'nightlife', 'lounge']):
                nightlife_count += 1
            elif any(word in text for word in ['restaurant', 'cafe', 'dining', 'food']):
                restaurant_count += 1
        
        if nightlife_count > restaurant_count:
            return 'nightlife'
        elif restaurant_count > 0:
            return 'restaurants'
        
        # По умолчанию
        return 'general'
    
    def _extract_places(self, soup: BeautifulSoup, article_type: str = 'general') -> List[Dict[str, Any]]:
        """Креативный метод извлечения мест из статьи в зависимости от типа"""
        places = []
        seen_titles = set()  # Для дедупликации
        
        # Применяем разные стратегии в зависимости от типа статьи
        if article_type == 'nightlife':
            places = self._extract_nightlife_places(soup, seen_titles)
        elif article_type == 'restaurants':
            places = self._extract_restaurant_places(soup, seen_titles)
        else:
            places = self._extract_general_places(soup, seen_titles)
        
        return places
    
    def _extract_nightlife_places(self, soup: BeautifulSoup, seen_titles: set) -> List[Dict[str, Any]]:
        """Специальный метод для извлечения ночных заведений с точным поиском описаний"""
        places = []
        
        # Метод 1: Ищем h2 заголовки (названия заведений)
        h2_tags = soup.find_all('h2')
        
        for h2 in h2_tags:
            title = h2.get_text().strip()
            
            # Очищаем название от "Photo:" и других префиксов
            if title.startswith('Photo:'):
                continue
            if 'Photo:' in title:
                title = title.split('Photo:')[0].strip()
            
            # Фильтруем названия
            if not self._is_valid_place_name(title) or len(title) < 3:
                continue
            
            # Дедупликация
            if title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())
            
            # Специальный поиск описания для ночных заведений
            description = self._find_description_for_place(h2)
            
            place = {
                'title': title,
                'detail_url': None,
                'teaser': description,
                'address_fallback': None,  # Не собираем адреса
                'hours_fallback': None,    # Не собираем часы
                'phone_fallback': None,    # Не собираем телефоны
                'number': len(places) + 1
            }
            places.append(place)
        
        # Метод 2: Ищем в заголовках h2 (для страниц типа "лучшие завтраки")
        h2_tags = soup.find_all('h2')
        
        for h2 in h2_tags:
            title = h2.get_text().strip()
            
            # Убираем префикс "Finalist:" если есть
            if title.lower().startswith('finalist:'):
                title = title[9:].strip()  # Убираем "Finalist:" и пробелы
            
            # Фильтруем названия
            if not self._is_valid_place_name(title) or len(title) < 3:
                continue
            
            # Дедупликация
            if title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())
            
            # Ищем описание для этого места
            description = self._find_description_for_place(h2)
            
            place = {
                'title': title,
                'detail_url': None,
                'teaser': description,
                'address_fallback': None,  # Не собираем адреса
                'hours_fallback': None,    # Не собираем часы
                'phone_fallback': None,    # Не собираем телефоны
                'number': len(places) + 1
            }
            places.append(place)
        
        return places
    
    def _extract_restaurant_places(self, soup: BeautifulSoup, seen_titles: set) -> List[Dict[str, Any]]:
        """Специальный метод для извлечения ресторанов с приоритетной проверкой названий"""
        places = []
        
        # Ищем h1 и h2 заголовки (названия ресторанов)
        h1_tags = soup.find_all('h1')
        h2_tags = soup.find_all('h2')
        all_headers = h1_tags + h2_tags
        
        for header in all_headers:
            title = header.get_text().strip()
            
            # Очищаем название от "Photo:" и других префиксов
            if title.startswith('Photo:'):
                continue
            if 'Photo:' in title:
                title = title.split('Photo:')[0].strip()
            
            # Исключаем служебные элементы
            excluded_titles = [
                'Leave a Comment', 'Latest News', 'New Places', 'Categories',
                'Information', 'Connect', 'Advertisement', 'Advertisement'
            ]
            if title in excluded_titles:
                continue
            
            if self._is_valid_place_name(title) and title not in seen_titles:
                seen_titles.add(title)
                
                # Используем приоритетный поиск описания с проверкой названия
                description = self._find_description_for_place(header)
                
                # Ищем адрес в следующем параграфе
                address = self._find_address_for_place(header)
                
                place = {
                    'title': title,
                    'teaser': description or '',
                    'address_fallback': address,
                    'phone_fallback': None,
                    'number': len(places) + 1
                }
                places.append(place)
        
        return places
    
    def _extract_general_places(self, soup: BeautifulSoup, seen_titles: set) -> List[Dict[str, Any]]:
        """Универсальный метод извлечения мест с приоритетной проверкой названий"""
        places = []
        
        # Метод 1: Ищем все жирные элементы (названия мест)
        bold_tags = soup.find_all(['b', 'strong'])
        
        for bold in bold_tags:
            title = bold.get_text().strip()
            
            if self._is_valid_place_name(title) and title not in seen_titles:
                seen_titles.add(title)
                
                # Используем приоритетный поиск описания с проверкой названия
                description = self._find_description_for_place(bold)
                
                # Ищем адрес
                address = self._find_address_for_place(bold)
                
                place = {
                    'title': title,
                    'teaser': description or '',
                    'address_fallback': address,
                    'phone_fallback': None,
                    'number': len(places) + 1
                }
                places.append(place)
        
        return places
    
    
    def _contains_place_name(self, text: str, place_name: str) -> bool:
        """Проверяет, содержит ли текст название места"""
        if not place_name or not text:
            return False
        
        # Очищаем название от лишних символов
        clean_name = place_name.replace('Photo:', '').replace('Photo', '').strip()
        
        # Разбиваем название на слова
        name_words = [word.strip() for word in clean_name.split() if len(word.strip()) > 2]
        
        if not name_words:
            return False
        
        text_lower = text.lower()
        
        # Проверяем, содержит ли текст хотя бы 2 слова из названия
        found_words = 0
        for word in name_words:
            if word.lower() in text_lower:
                found_words += 1
        
        # Если найдено больше половины слов из названия - это наше описание
        return found_words >= len(name_words) // 2 + 1
    
    def _find_address_for_place(self, bold_elem) -> Optional[str]:
        """Поиск адреса для места"""
        # Простой поиск адреса в следующем элементе
        next_elem = bold_elem.find_next(['p', 'div'])
        if next_elem and next_elem.get_text().strip():
            text = next_elem.get_text().strip()
            # Ищем адресные индикаторы
            address_indicators = ['road', 'soi', 'street', 'avenue', 'bangkok', 'thailand']
            if any(indicator in text.lower() for indicator in address_indicators):
                return text
        return None
    
    def _find_description_for_place(self, bold_elem) -> Optional[str]:
        """ГИБРИДНЫЙ поиск описания: креативный алгоритм + GPT-помощник"""
        place_name = bold_elem.get_text().strip()
        
        # ЭТАП 1: Креативный алгоритм (быстрый)
        description = self._find_description_creative(bold_elem, place_name)
        
        if description:
            # Проверяем качество описания
            if self._contains_place_name(description, place_name):
                return description  # Хорошее описание с названием места
            else:
                # Описание найдено, но без названия - пробуем GPT для лучшего
                gpt_description = self._find_description_with_gpt(bold_elem, place_name)
                if gpt_description and self._contains_place_name(gpt_description, place_name):
                    return gpt_description  # GPT нашел лучшее описание
                else:
                    # Если GPT не нашел лучшее, проверяем качество креативного описания
                    if self._is_good_description(description, place_name):
                        return description  # Креативное описание достаточно хорошее
                    else:
                        # Креативное описание плохое, пробуем GPT как fallback
                        gpt_fallback = self._find_description_with_gpt(bold_elem, place_name)
                        return gpt_fallback if gpt_fallback else description
        
        # ЭТАП 2: GPT-помощник (умный) для сложных случаев
        description = self._find_description_with_gpt(bold_elem, place_name)
        if description:
            return description
        
        return None
    
    def _is_good_description(self, description: str, place_name: str) -> bool:
        """Проверяет, является ли описание хорошим для места"""
        if not description or len(description) < 100:
            return False
        
        # Проверяем, что это не общий текст статьи
        article_indicators = [
            'our big breakfast list is back',
            'this year we are happy to introduce',
            'the breakfast issue is a big deal',
            'you love it we love it',
            'jump to:',
            'back to top',
            'by bk staff',
            'bangkok things to-do',
            'for fans of bangkok cafes',
            'so many restaurants come and go',
            'it was a big win for the sukhumvit',
            'there are four holey bakery outlets',
            'despite being hidden away',
            'from the minds behind bangkok'
        ]
        
        description_lower = description.lower()
        if any(indicator in description_lower for indicator in article_indicators):
            return False
        
        # Проверяем, что описание содержит информацию о заведении
        venue_indicators = [
            'serves', 'offers', 'specializes', 'features', 'located',
            'menu', 'food', 'drink', 'coffee', 'breakfast', 'lunch',
            'dinner', 'price', 'cost', 'bath', 'baht', 'b120', 'b150',
            'b200', 'b300', 'b400', 'b500', 'b600', 'b700', 'b800',
            'b900', 'b1000', 'restaurant', 'cafe', 'bakery', 'bar',
            'kitchen', 'dining', 'eatery', 'spot', 'venue', 'place'
        ]
        
        venue_count = sum(1 for indicator in venue_indicators if indicator in description_lower)
        
        # Более гибкая логика для определения хорошего описания
        if venue_count >= 3:
            return True
        elif venue_count >= 2 and len(description) > 200:
            return True
        elif venue_count >= 1 and len(description) > 400:
            return True
        
        return False
    
    def _find_description_creative(self, bold_elem, place_name: str) -> Optional[str]:
        """Креативный поиск описания с умным контекстом и приоритизацией"""
        # Создаем зоны поиска с приоритетами
        search_zones = self._create_search_zones(bold_elem)
        
        # ПРИОРИТЕТ 1: Поиск с проверкой названия места (самый надежный)
        for zone in search_zones:
            for element in zone['elements']:
                text = element.get_text().strip()
                if len(text) > 100 and self._is_venue_description(text):
                    if self._contains_place_name(text, place_name):
                        description = self._clean_description_text(text)
                        if len(description) > 50:
                            return description
        
        # ПРИОРИТЕТ 2: Fallback без проверки названия (если не нашли с проверкой)
        for zone in search_zones:
            for element in zone['elements']:
                text = element.get_text().strip()
                if len(text) > 100 and self._is_venue_description(text):
                    description = self._clean_description_text(text)
                    if len(description) > 50:
                        return description
        
        return None
    
    def _find_description_with_gpt(self, bold_elem, place_name: str) -> Optional[str]:
        """УМНЫЙ GPT-помощник для поиска описаний"""
        try:
            import openai
            
            # Создаем ограниченный HTML контекст (максимум 1500 токенов)
            html_context = self._create_smart_html_context(bold_elem, place_name)
            
            # Создаем GPT клиент
            client = openai.OpenAI(api_key="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")
            
            # ЧЕТКИЙ ПРОМПТ для GPT
            prompt = f"""АНАЛИЗ HTML ДЛЯ ПОИСКА ОПИСАНИЯ МЕСТА

ЗАДАЧА: Найди описание для места "{place_name}"

HTML КОНТЕКСТ:
{html_context}

ИНСТРУКЦИИ:
1. Найди текст, который описывает место "{place_name}"
2. Текст должен быть длиннее 100 символов
3. Текст должен содержать информацию о заведении (еда, напитки, атмосфера, услуги, адрес, часы работы)
4. Исключи рекламные тексты, навигацию, меню сайта
5. Исключи тексты о других местах

ФОРМАТ ОТВЕТА:
- Если нашел описание: верни ТОЛЬКО найденный текст
- Если не нашел: верни "NOT_FOUND"

ОПИСАНИЕ:"""
            
            # Вызываем GPT с ограничениями
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Ты эксперт по анализу HTML и поиску описаний заведений. Отвечай кратко и точно."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Низкая температура для точности
                max_tokens=500,   # Ограничиваем ответ
                timeout=10        # Быстрый таймаут
            )
            
            result = response.choices[0].message.content.strip()
            
            # Валидация результата
            if result and result != "NOT_FOUND" and len(result) > 50:
                # Проверяем, что это действительно описание заведения
                if self._is_venue_description(result):
                    return self._clean_description_text(result)
            
        except Exception as e:
            print(f"GPT-помощник ошибка для {place_name}: {e}")
        
        return None
    
    def _create_smart_html_context(self, bold_elem, place_name: str) -> str:
        """Создает УМНЫЙ HTML контекст для GPT (расширенный)"""
        from bs4 import BeautifulSoup
        
        # Создаем расширенный контекст из элементов вокруг места
        context_elements = []
        
        # Добавляем само место
        context_elements.append(str(bold_elem))
        
        # Идем вперед на 25 элементов
        current = bold_elem
        for _ in range(25):
            current = current.find_next()
            if not current:
                break
            if hasattr(current, 'get_text') and current.get_text().strip():
                context_elements.append(str(current))
        
        # Объединяем контекст
        html_context = '\n'.join(context_elements)
        
        # Очищаем HTML для лучшего понимания GPT
        soup = BeautifulSoup(html_context, 'html.parser')
        text = soup.get_text()
        
        # Ограничиваем размер (примерно 3000 токенов)
        if len(text) > 4000:
            text = text[:4000] + "..."
        
        return text
    
    def _create_html_context(self, bold_elem) -> str:
        """Создает HTML контекст вокруг места для GPT (старая версия)"""
        from bs4 import BeautifulSoup
        
        # Находим родительский контейнер
        parent = bold_elem.parent
        if not parent:
            parent = bold_elem
        
        # Создаем контекст из 20 элементов вокруг места
        context_elements = []
        current = bold_elem
        
        # Идем назад на 5 элементов
        for _ in range(5):
            current = current.previous_sibling
            if not current:
                break
            if hasattr(current, 'get_text') and current.get_text().strip():
                context_elements.append(str(current))
        
        # Добавляем само место
        context_elements.append(str(bold_elem))
        
        # Идем вперед на 15 элементов
        current = bold_elem
        for _ in range(15):
            current = current.next_sibling
            if not current:
                break
            if hasattr(current, 'get_text') and current.get_text().strip():
                context_elements.append(str(current))
        
        # Объединяем контекст
        html_context = '\n'.join(context_elements)
        
        # Очищаем HTML для лучшего понимания GPT
        soup = BeautifulSoup(html_context, 'html.parser')
        return soup.get_text()[:2000]  # Ограничиваем размер
    
    def _create_search_zones(self, bold_elem) -> list:
        """Создает зоны поиска с приоритетами для креативного поиска"""
        zones = []
        
        # ЗОНА 1: Ближайшие элементы (высший приоритет)
        zone1_elements = []
        
        # 1.1. Следующий div
        next_div = bold_elem.find_next('div')
        if next_div and next_div.get_text().strip():
            zone1_elements.append(next_div)
        
        # 1.2. Следующий p
        next_p = bold_elem.find_next('p')
        if next_p and next_p.get_text().strip():
            zone1_elements.append(next_p)
        
        # 1.3. Родительский контейнер
        if bold_elem.parent:
            for elem in bold_elem.parent.find_all(['p', 'div'], recursive=False):
                if elem != bold_elem and elem.get_text().strip():
                    zone1_elements.append(elem)
        
        if zone1_elements:
            zones.append({
                'name': 'Ближайшие элементы',
                'priority': 1,
                'elements': zone1_elements
            })
        
        # ЗОНА 2: Расширенный поиск (средний приоритет)
        zone2_elements = []
        current = bold_elem
        for _ in range(5):  # Следующие 5 элементов
            current = current.find_next()
            if not current:
                break
            if current.name in ['img', 'br', 'hr'] or not current.get_text().strip():
                continue
            if current.name in ['p', 'div', 'span']:
                zone2_elements.append(current)
        
        if zone2_elements:
            zones.append({
                'name': 'Расширенный поиск',
                'priority': 2,
                'elements': zone2_elements
            })
        
        # ЗОНА 3: Дальний поиск (низкий приоритет)
        zone3_elements = []
        current = bold_elem
        for _ in range(10):  # Следующие 10 элементов
            current = current.find_next()
            if not current:
                break
            if current.name in ['img', 'br', 'hr'] or not current.get_text().strip():
                continue
            if current.name in ['p', 'div', 'span']:
                zone3_elements.append(current)
        
        if zone3_elements:
            zones.append({
                'name': 'Дальний поиск',
                'priority': 3,
                'elements': zone3_elements
            })
        
        return zones
    
    def _is_venue_description(self, text: str) -> bool:
        """КРЕАТИВНАЯ проверка, является ли текст описанием заведения"""
        if not text or len(text) < 100:
            return False
        
        text_lower = text.lower()
        
        # Исключаем рекламные тексты (умный фильтр)
        excluded_phrases = [
            'want the very best stories from bk magazine',
            'sign up for bk weekly',
            'stay up to date on what\'s new and cool',
            'delivered straight to your inbox',
            'bk magazine is a coconuts media publication',
            'copyright © 2020 coconuts media limited',
            'terms of service', 'privacy policy',
            'advertise with us', 'join on facebook',
            'follow on twitter', 'contact us',
            'subscribe', 'newsletter',
            'delivered straight', 'inbox every thursday',
            'want the very best', 'stories from bk',
            'thursday afternoon', 'cool in bangkok'
        ]
        
        for phrase in excluded_phrases:
            if phrase in text_lower:
                return False
        
        # Дополнительная проверка на рекламный контент
        if 'bk magazine' in text_lower and len(text) < 200:
            return False
        
        # Расширенные индикаторы описания заведения
        venue_indicators = [
            # Основные типы заведений
            'bar', 'restaurant', 'hotel', 'rooftop', 'venue', 'spot', 'place',
            'cafe', 'coffee', 'bakery', 'deli', 'bistro', 'pub', 'lounge',
            'club', 'nightclub', 'disco', 'karaoke', 'spa', 'salon', 'gym',
            'museum', 'gallery', 'theater', 'cinema', 'mall', 'shop', 'store',
            
            # Описательные слова
            'floor', 'building', 'view', 'atmosphere', 'ambiance', 'experience',
            'interior', 'design', 'decor', 'style', 'vibe', 'mood', 'feeling',
            'location', 'area', 'district', 'neighborhood', 'street', 'soi',
            
            # Еда и напитки
            'cocktail', 'drink', 'food', 'menu', 'cuisine', 'chef', 'kitchen',
            'pizza', 'pasta', 'italian', 'french', 'japanese', 'thai', 'indian',
            'chinese', 'korean', 'mexican', 'mediterranean', 'fine dining',
            'comfort food', 'brunch', 'breakfast', 'lunch', 'dinner', 'supper',
            'wine', 'beer', 'coffee', 'dessert', 'snack', 'appetizer', 'main',
            
            # Время работы и активность
            'open', 'daily', 'pm', 'am', 'midnight', 'late', 'night', 'dining',
            'hours', 'time', 'schedule', 'available', 'serving', 'offering',
            
            # Специальные характеристики
            'award', 'awarded', 'winner', 'best', 'top', 'famous', 'popular',
            'recommended', 'featured', 'highlighted', 'notable', 'special',
            'unique', 'exclusive', 'premium', 'luxury', 'upscale', 'casual',
            'romantic', 'cozy', 'intimate', 'spacious', 'outdoor', 'indoor',
            'terrace', 'balcony', 'patio', 'garden', 'pool', 'beach'
        ]
        
        # Считаем количество индикаторов
        venue_count = sum(1 for indicator in venue_indicators if indicator in text_lower)
        
        # КРЕАТИВНАЯ ЛОГИКА:
        # 1. Если есть 3+ индикатора - это точно описание заведения
        if venue_count >= 3:
            return True
        
        # 2. Если есть 2+ индикатора И длина > 200 - это описание заведения
        if venue_count >= 2 and len(text) > 200:
            return True
        
        # 3. Если есть 1+ индикатор И длина > 400 - это может быть описание заведения
        if venue_count >= 1 and len(text) > 400:
            return True
        
        # 4. Дополнительные проверки для коротких текстов
        if len(text) >= 100 and len(text) <= 200:
            # Проверяем на наличие ключевых фраз
            key_phrases = [
                'should be no stranger', 'fans of', 'earned the top spot',
                'keeps refining', 'best-in-class', 'located on the',
                'offers panoramic', 'stunning views', 'substandard drinks',
                'not the case', 'sit downstairs', 'upstairs for',
                'can be paired', 'tonic of your choosing'
            ]
            
            for phrase in key_phrases:
                if phrase in text_lower:
                    return True
        
        return False
    
    
    def _is_valid_place_name(self, title: str) -> bool:
        """Проверка валидности названия места"""
        if not title or len(title) < 3:
            return False
        
        # Исключаем только явно служебные слова
        service_words = {
            'finalist', 'winner', 'award', 'awards', 'best', 'top', 'new', 'opening', 'opened',
            'photo', 'image', 'credit', 'courtesy', 'source', 'facebook', 'instagram', 'twitter',
            'neighborhood:', 'vibe:', 'price:', 'neighborhood', 'vibe', 'price'
        }
        
        # Проверяем на служебные слова
        title_lower = title.lower()
        for word in service_words:
            if title_lower == word or title_lower.startswith(word + ' '):
                return False
        
        # Исключаем только явно технические паттерны
        technical_patterns = [
            r'^\d+$',  # Только цифры
            r'^[a-z]{1,2}$',  # Одна-две буквы
            r'^[^a-zA-Z]*$',  # Без букв
            r'^(photo|image|credit|courtesy)',  # Технические префиксы
        ]
        
        for pattern in technical_patterns:
            if re.match(pattern, title_lower):
                return False
        
        # Исключаем названия с технической информацией (только в контексте)
        technical_indicators = [
            'open daily', 'open monday', 'open tuesday', 'open wednesday',
            'open thursday', 'open friday', 'open saturday', 'open sunday',
            'phone', 'tel', 'address', 'location', 'hours', 'closed',
            'road.', 'soi.', 'floor.', 'pm.', 'am.'
        ]
        
        # Проверяем только полные фразы, а не отдельные слова
        for indicator in technical_indicators:
            if indicator in title_lower:
                return False
        
        # Исключаем слишком длинные названия (вероятно адреса или описания)
        if len(title) > 50:  # Уменьшили с 200 до 50
            return False
        
        # Исключаем названия с невидимыми символами
        if title.startswith('​') or title.endswith('​'):
            return False
        
        return True
    
    
    def _is_service_text(self, text: str) -> bool:
        """Умная проверка, является ли текст служебным"""
        if not text or len(text) < 50:
            return True
        
        text_lower = text.lower()
        
        # Если текст содержит описание заведения - это не служебный текст
        venue_indicators = [
            'bar', 'restaurant', 'hotel', 'rooftop', 'venue', 'spot', 'place',
            'floor', 'building', 'view', 'cocktail', 'drink', 'food', 'menu',
            'open', 'daily', 'pm', 'am', 'midnight', 'late', 'night'
        ]
        
        venue_count = sum(1 for indicator in venue_indicators if indicator in text_lower)
        if venue_count >= 2:  # Если есть 2+ индикатора заведения - это описание
            return False
        
        # Проверяем на служебные индикаторы только в контексте вводных абзацев
        service_indicators = [
            'bangkok likes to party',
            'this year, we\'ve got',
            'annual bad awards',
            'media junket',
            'promotional vehicle',
            'opening in just',
            'crack this list',
            'gleaming high rises'
        ]
        
        # Если текст короткий и содержит только служебные фразы
        if len(text) < 200:
            for indicator in service_indicators:
                if indicator in text_lower:
                    return True
        
        return False
    
    
    def _clean_description_text(self, text: str) -> str:
        """Очистка текста описания от адресов и телефонов"""
        # Удаляем адреса
        text = re.sub(r'\d+/F.*?(?=\s|$)', '', text)
        text = re.sub(r'\d+.*?Soi.*?(?=\s|$)', '', text)
        text = re.sub(r'\d+.*?Sukhumvit.*?(?=\s|$)', '', text)
        text = re.sub(r'\d+.*?Sathorn.*?(?=\s|$)', '', text)
        text = re.sub(r'\d+.*?Wireless.*?(?=\s|$)', '', text)
        
        # Удаляем телефоны
        text = re.sub(r'0[0-9-\\s]{8,}', '', text)
        
        # Удаляем часы работы
        text = re.sub(r'Open.*?(?=\s|$)', '', text)
        text = re.sub(r'Daily.*?(?=\s|$)', '', text)
        
        # Очищаем от лишних пробелов
        text = re.sub(r'\\s+', ' ', text).strip()
        
        return text if len(text) > 20 else ""
    
    
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

    def parse_catalog_page(self, catalog_url: str, max_pages: int = None) -> List[Dict[str, Any]]:
        """
        Парсит страницы каталога BK Magazine и извлекает ссылки на статьи
        
        Args:
            catalog_url: URL страницы каталога (например, search-news?type=restaurant)
            max_pages: Максимальное количество страниц для парсинга (None = все)
            
        Returns:
            List[Dict]: Список словарей с информацией о статьях
        """
        all_articles = []
        page = 0
        
        while True:
            # Формируем URL страницы
            if page == 0:
                url = catalog_url
            else:
                separator = '&' if '?' in catalog_url else '?'
                url = f"{catalog_url}{separator}page={page}"
            
            print(f"📄 Парсинг страницы {page}: {url}")
            
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Ищем H5 заголовки (названия ресторанов)
                h5_tags = soup.find_all('h5')
                
                if not h5_tags:
                    print(f"   ❌ Страница {page} пустая - завершаем парсинг")
                    break
                
                page_articles = []
                
                for h5 in h5_tags:
                    restaurant_name = h5.get_text().strip()
                    
                    # Ищем ссылку на полную статью
                    article_link = None
                    parent = None
                    
                    # Сначала ищем в самом H5
                    h5_link = h5.find('a')
                    if h5_link and h5_link.get('href'):
                        article_link = h5_link.get('href')
                    else:
                        # Ищем в родительском div
                        parent = h5.parent
                        if parent:
                            parent_link = parent.find('a', href=True)
                            if parent_link and parent_link.get('href').startswith('/restaurants/'):
                                article_link = parent_link.get('href')
                    
                    if article_link:
                        # Преобразуем относительную ссылку в абсолютную
                        if article_link.startswith('/'):
                            article_link = f"https://bk.asia-city.com{article_link}"
                        
                        # Извлекаем краткое описание из родительского div
                        description = ""
                        if parent:
                            # Ищем описание в тексте родительского div
                            parent_text = parent.get_text()
                            lines = parent_text.split('\n')
                            for line in lines:
                                line = line.strip()
                                if line and line != restaurant_name and not line.startswith('Restaurant') and not 'ago' in line:
                                    description = line
                                    break
                        
                        page_articles.append({
                            'title': restaurant_name,
                            'article_url': article_link,
                            'description': description,
                            'category': 'Restaurant'
                        })
                
                print(f"   ✅ Найдено {len(page_articles)} ресторанов на странице {page}")
                all_articles.extend(page_articles)
                
                # Проверяем ограничение по страницам
                if max_pages and page >= max_pages - 1:
                    print(f"   🛑 Достигнуто ограничение {max_pages} страниц")
                    break
                
                page += 1
                
            except Exception as e:
                print(f"   ❌ Ошибка парсинга страницы {page}: {e}")
                break
        
        print(f"\\n📊 ИТОГО НАЙДЕНО СТАТЕЙ: {len(all_articles)}")
        return all_articles

    def parse_catalog_articles(self, catalog_url: str, limit: int = None, max_pages: int = None) -> List[Dict[str, Any]]:
        """
        Парсит каталог и все статьи в нем
        
        Args:
            catalog_url: URL страницы каталога
            limit: Ограничение количества статей (опционально)
            max_pages: Максимальное количество страниц для парсинга (опционально)
            
        Returns:
            List[Dict]: Список всех мест из всех статей каталога
        """
        print(f"🔍 Парсинг каталога: {catalog_url}")
        if max_pages:
            print(f"📄 Ограничение страниц: {max_pages}")
        
        # Получаем список статей из каталога
        articles = self.parse_catalog_page(catalog_url, max_pages=max_pages)
        print(f"📰 Найдено статей: {len(articles)}")
        
        if limit:
            articles = articles[:limit]
            print(f"📝 Ограничено до: {len(articles)} статей")
        
        all_places = []
        
        # Парсим каждую статью
        for i, article in enumerate(articles, 1):
            print(f"\\n📖 Статья {i}/{len(articles)}: {article['title']}")
            
            try:
                places = self.parse_article_page(article['article_url'])
                print(f"   Найдено мест: {len(places)}")
                
                # Добавляем информацию о статье к каждому месту
                for place in places:
                    place['article_title'] = article['title']
                    place['article_url'] = article['article_url']
                
                all_places.extend(places)
                
            except Exception as e:
                print(f"   ❌ Ошибка парсинга статьи: {e}")
                continue
        
        print(f"\\n📊 ИТОГО НАЙДЕНО МЕСТ: {len(all_places)}")
        return all_places


def test_parser():
    """Тестовая функция для проверки парсера"""
    adapter = BKMagazineAdapter()
    
    # Тестируем на реальной странице
    test_url = 'https://bk.asia-city.com/nightlife/article/bangkoks-best-rooftop-bars'
    
    print(f"Тестируем парсер BK Magazine на: {test_url}")
    places = adapter.parse_article_page(test_url)
    
    print(f"\\nНайдено мест: {len(places)}")
    
    # Показываем статистику по описаниям
    places_with_desc = [p for p in places if p['teaser']]
    print(f"Мест с описаниями: {len(places_with_desc)}/{len(places)}")
    
    for i, place in enumerate(places[:5], 1):
        print(f"\\n{i}. {place['title']}")
        print(f"   Описание: {place['teaser'] or 'Нет'}")


if __name__ == "__main__":
    test_parser()
