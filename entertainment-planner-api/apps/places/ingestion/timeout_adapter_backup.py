"""
TimeOut Bangkok парсер для сбора данных о местах
Следует спецификации MVP для парсинга TimeOut
"""
import re
import time
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse
import logging

logger = logging.getLogger(__name__)


class TimeOutAdapter:
    """Адаптер для парсинга TimeOut Bangkok"""
    
    def __init__(self, base_url: str = "https://www.timeout.com", rate_limit: float = 1.0):
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
            response = self.session.get(url, timeout=30)
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
        
        # Удаляем элементы с техническими классами
        technical_classes = [
            'ad', 'advertisement', 'social', 'share', 'footer', 'header',
            'navigation', 'nav', 'menu', 'sidebar', 'widget', 'cookie',
            'popup', 'modal', 'overlay', 'banner', 'promo', 'newsletter'
        ]
        
        for class_name in technical_classes:
            elements = soup.find_all(class_=re.compile(class_name, re.IGNORECASE))
            for element in elements:
                element.decompose()
    
    def parse_list_page(self, list_url: str) -> List[Dict]:
        """
        Парсинг страницы списка мест
        Возвращает список словарей с данными для детального парсинга
        """
        soup = self._make_request(list_url)
        if not soup:
            return []
        
        places = []
        
        # Метод 1: Оригинальный поиск по ссылкам
        places.extend(self._extract_original_links(soup))
        
        # Метод 2: Поиск в контейнерах списков
        places.extend(self._extract_from_containers(soup))
        
        # Метод 3: Поиск по ссылкам на рестораны
        places.extend(self._extract_restaurant_links(soup))
        
        # Метод 4: Поиск по JSON-LD структурам
        places.extend(self._extract_from_json_ld(soup))
        
        # Удаляем дубликаты
        places = self._remove_duplicates(places)
        
        return places
    
    def _extract_original_links(self, soup: BeautifulSoup) -> List[Dict]:
        """Оригинальный метод поиска ссылок"""
        places = []
        
        # Ищем основной контент статьи
        main_content = soup.find('main') or soup.find('article')
        if not main_content:
            return places
        
        # Ищем ссылки на рестораны/кафе в основном контенте
        restaurant_links = main_content.find_all('a', href=re.compile(r'/bangkok/restaurants/'))
        
        # Фильтруем только реальные места (исключаем социальные сети, кнопки)
        seen_urls = set()
        filtered_links = []
        
        for link in restaurant_links:
            title = link.get_text().strip()
            href = link.get('href', '')
            
            # Исключаем социальные сети и служебные ссылки
            if any(social in href.lower() for social in ['facebook', 'twitter', 'pinterest', 'whatsapp', 'mailto']):
                continue
            
            # Исключаем короткие названия и служебные тексты
            # Но разрешаем ссылки с номерами (1. Place Name)
            if not re.match(r'^\d+\.\s+', title) and not self._is_valid_place_title(title):
                continue
            
            # Исключаем дубликаты по URL
            full_url = urljoin(self.base_url, href)
            if full_url in seen_urls:
                continue
            
            # Приоритет: берем ссылки с номерами (1. Place Name) вместо "Photograph: ..."
            if re.match(r'^\d+\.\s+', title):
                # Это ссылка с номером - добавляем
                seen_urls.add(full_url)
                filtered_links.append(link)
            elif full_url not in seen_urls:
                # Это другая ссылка на то же место - добавляем только если еще не было ссылки с номером
                seen_urls.add(full_url)
                filtered_links.append(link)
        
        for i, link in enumerate(filtered_links, 1):
            try:
                # Получаем название из текста ссылки и очищаем его
                title = self._clean_title(link.get_text().strip())
                
                # Получаем URL
                detail_url = urljoin(self.base_url, link['href'])
                
                # Ищем описание рядом со ссылкой
                teaser = self._extract_teaser_near_link(link)
                
                # Извлекаем адрес и часы (fallback)
                address, hours = self._extract_address_hours_fallback(link)
                
                places.append({
                    'title': title,
                    'detail_url': detail_url,
                    'teaser': teaser,
                    'address_fallback': address,
                    'hours_fallback': hours,
                    'number': i
                })
                
            except Exception as e:
                logger.error(f"Ошибка парсинга ссылки: {e}")
                continue
        
        logger.info(f"Найдено {len(places)} мест на странице списка")
        
        # Логируем первые несколько мест для отладки
        for i, place in enumerate(places[:3], 1):
            logger.info(f"Место {i}: {place['title'][:50]}...")
        
        return places
    
    def _extract_teaser_near_link(self, link) -> Optional[str]:
        """Извлечение краткого описания рядом со ссылкой"""
        # Ищем описание в родительском элементе или соседних
        parent = link.parent
        if parent:
            # Ищем текст в родительском элементе, исключая саму ссылку
            text_parts = []
            for elem in parent.find_all(text=True, recursive=True):
                if elem.parent != link:  # Исключаем текст самой ссылки
                    text = elem.strip()
                    if text and len(text) > 20:  # Только значимый текст
                        text_parts.append(text)
            
            if text_parts:
                return ' '.join(text_parts[:2])  # Берем первые 2 части
        
        return None
    
    def _is_valid_place_title(self, title: str) -> bool:
        """Проверяет, является ли заголовок валидным названием места"""
        if not title or len(title) < 3:
            return False
        
        # Исключаем служебные слова и технические тексты
        service_words = [
            'read more', 'photograph:', 'javascript is not available', 'pin builder',
            'home', 'about', 'contact', 'privacy', 'terms', 'login', 'signup',
            'menu', 'search', 'subscribe', 'newsletter', 'advertise', 'careers',
            'timeout bangkok', 'entertainment guide', 'best new cafes', 'restaurants',
            'modern slavery statement', 'pdf', 'target', 'blank', 'class',
            'viewbox', 'svg', 'xmlns', 'stroke', 'fill', 'none', 'round',
            'width', 'height', 'd', 'path', 'circle', 'rect', 'polygon'
        ]
        
        title_lower = title.lower()
        if any(service in title_lower for service in service_words):
            return False
        
        # Исключаем технические паттерны
        technical_patterns = [
            r'^[<>].*[<>]$',  # HTML теги
            r'^[a-z]+://',    # URL
            r'^[a-z]+\.[a-z]+',  # домены
            r'^[0-9a-f]{8,}',   # хеши
            r'^[a-z]+_[a-z]+',  # snake_case
            r'^[A-Z][a-z]+[A-Z][a-z]+',  # camelCase
            r'^[A-Z]{2,}',     # ВСЕ ЗАГЛАВНЫЕ
            r'^[a-z]{2,}',     # все строчные
            r'^[0-9\s\.]+$',   # только цифры и точки
            r'^[^\w\s]+$',     # только символы
        ]
        
        for pattern in technical_patterns:
            if re.match(pattern, title):
                return False
        
        # Проверяем на паттерны названий мест
        place_patterns = [
            r'\d+\.\s*[A-Z][a-zA-Z\s&]+',  # "1. Place Name"
            r'[A-Z][a-zA-Z\s&]+(?:Cafe|Restaurant|Bar|Pub|Club|Spa|Hotel|Coffee|Bistro|Diner|Eatery|Grill)',
            r'[A-Z][a-zA-Z\s&]+(?:Café|Bistro|Diner|Eatery|Grill)',
            r'^[A-Z][a-zA-Z\s&]+$'  # Простое название с заглавной буквы
        ]
        
        for pattern in place_patterns:
            if re.search(pattern, title):
                return True
        
        # Дополнительная проверка: текст должен содержать буквы и быть читаемым
        if len(title) > 50:  # Слишком длинные названия
            return False
        
        if not re.search(r'[a-zA-Z]', title):  # Должны быть буквы
            return False
        
        return True
    
    def _clean_title(self, title: str) -> str:
        """Очищает название от номеров и лишних символов"""
        if not title:
            return ""
        
        # Убираем номер в начале (например, "1. Place Name" -> "Place Name")
        title = re.sub(r'^\d+\.\s*', '', title)
        
        # Убираем лишние пробелы
        title = title.strip()
        
        # Убираем HTML-сущности
        title = title.replace('&amp;', '&')
        title = title.replace('&lt;', '<')
        title = title.replace('&gt;', '>')
        title = title.replace('&quot;', '"')
        title = title.replace('&#39;', "'")
        
        return title
    
    def _extract_address_hours_fallback(self, item) -> Tuple[Optional[str], Optional[str]]:
        """Извлечение адреса и часов из fallback (строка Address: ... Open ...)"""
        # Ищем строку вида "Address: ... Open ..."
        text_content = item.get_text()
        
        # Регулярка для извлечения адреса и часов
        pattern = r'Address:\s*(.+?)\.\s*(Open[^.]*|Opening hours:[^.]*)\.?'
        match = re.search(pattern, text_content, re.DOTALL)
        
        if match:
            address = match.group(1).strip()
            hours = match.group(2).strip()
            return address, hours
        
        return None, None
    
    def parse_detail_page(self, detail_url: str) -> Optional[Dict]:
        """
        Парсинг детальной страницы места
        Возвращает полные данные места
        """
        soup = self._make_request(detail_url)
        if not soup:
            return None
        
        try:
            # Название (h1)
            title_elem = soup.find('h1')
            title = title_elem.get_text().strip() if title_elem else None
            
            if not title:
                logger.warning(f"Не найдено название на странице {detail_url}")
                return None
            
            # Категория и район (строка под h1)
            category, area = self._extract_category_area(soup)
            
            # Полное описание (блок "Time Out says")
            description_full = self._extract_timeout_says(soup)
            
            # Адрес, часы, Google Maps из раздела Details
            address, hours_text, gmaps_url = self._extract_details(soup)
            
            # Изображение
            image_url = self._extract_image_url(soup)
            
            # Координаты из data-zone-location-info
            lat, lng = self._extract_coordinates(soup)
            
            return {
                'name': title,
                'category': category,
                'area': area,
                'description_full': description_full,
                'address': address,
                'hours_text': hours_text,
                'gmaps_url': gmaps_url,
                'picture_url': image_url,
                'lat': lat,
                'lng': lng,
                'source': 'timeout',
                'source_url': detail_url,
                'raw_payload': str(soup.find('body')) if soup.find('body') else None,
                'scraped_at': time.time()
            }
            
        except Exception as e:
            logger.error(f"Ошибка парсинга детальной страницы {detail_url}: {e}")
            return None
    
    def _extract_category_area(self, soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
        """Извлечение категории и района"""
        # Ищем теги с классом _text_1i2cm_68 (категория и район)
        category_tags = soup.find_all('span', class_='_text_1i2cm_68')
        
        category = None
        area = None
        
        for tag in category_tags:
            text = tag.get_text().strip()
            if '|' in text:
                # Это категория вида "Restaurants | Cafés"
                parts = text.split('|')
                if len(parts) >= 2:
                    category = parts[0].strip()
            elif text and not text.isdigit() and len(text) > 2:
                # Это район (например, "Thonglor")
                area = text
        
        # Fallback: ищем в мета-тегах
        if not category:
            meta_category = soup.find('meta', {'property': 'article:section'})
            if meta_category:
                category = meta_category.get('content', '')
        
        return category, area
    
    def _extract_timeout_says(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлечение блока 'Time Out says'"""
        # Ищем заголовок "Time Out says"
        timeout_says = soup.find('h3', string=re.compile(r'Time Out says', re.I))
        if not timeout_says:
            # Fallback: ищем в других вариантах
            timeout_says = soup.find(string=re.compile(r'Time Out says', re.I))
            if timeout_says:
                timeout_says = timeout_says.parent
        
        if not timeout_says:
            return None
        
        # Ищем контейнер с описанием
        content_div = timeout_says.find_next('div', class_='_content_1t3mx_1')
        if content_div:
            # Собираем все параграфы в контейнере
            description_parts = []
            for p in content_div.find_all('p'):
                text = p.get_text().strip()
                if text:
                    description_parts.append(text)
            
            if description_parts:
                return ' '.join(description_parts)
        
        # Fallback: собираем все параграфы после заголовка
        description_parts = []
        current = timeout_says.find_next_sibling()
        
        while current and current.name not in ['h1', 'h2', 'h3', 'h4']:
            if current.name == 'p' and current.get_text().strip():
                description_parts.append(current.get_text().strip())
            current = current.find_next_sibling()
        
        return ' '.join(description_parts) if description_parts else None
    
    def _extract_details(self, soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Извлечение адреса, часов и Google Maps из раздела Details"""
        # Ищем раздел Details
        details_section = soup.find('h3', string=re.compile(r'Details', re.I))
        if not details_section:
            return None, None, None
        
        address = None
        hours_text = None
        gmaps_url = None
        
        # Ищем адрес в структуре dl/dt/dd
        address_dt = details_section.find_next('dt', string=re.compile(r'Address', re.I))
        if address_dt:
            address_dd = address_dt.find_next_sibling('dd')
            if address_dd:
                # Собираем все dd элементы после dt
                address_parts = []
                current = address_dd
                while current and current.name == 'dd':
                    text = current.get_text().strip()
                    if text:
                        address_parts.append(text)
                    current = current.find_next_sibling()
                
                if address_parts:
                    address = ', '.join(address_parts)
        
        # Ищем часы работы в структуре dl/dt/dd
        hours_dt = details_section.find_next('dt', string=re.compile(r'Opening hours', re.I))
        if hours_dt:
            hours_dd = hours_dt.find_next_sibling('dd')
            if hours_dd:
                hours_text = hours_dd.get_text().strip()
        
        # Ищем ссылку Directions (Google Maps)
        directions_link = soup.find('a', string=re.compile(r'Directions', re.I))
        if directions_link:
            gmaps_url = directions_link.get('href')
        
        return address, hours_text, gmaps_url
    
    def _extract_coordinates(self, soup: BeautifulSoup) -> Tuple[Optional[float], Optional[float]]:
        """Извлечение координат из data-zone-location-info"""
        try:
            # Ищем элемент с data-zone-location-info
            zone_elem = soup.find(attrs={'data-zone-location-info': True})
            if not zone_elem:
                return None, None
            
            # Получаем JSON из атрибута
            zone_data = zone_elem.get('data-zone-location-info')
            if not zone_data:
                return None, None
            
            # Парсим JSON
            import json
            zone_info = json.loads(zone_data)
            
            # Извлекаем координаты из zones
            if 'zones' in zone_info and zone_info['zones']:
                zone = zone_info['zones'][0]  # Берем первую зону
                lat = zone.get('latitude')
                lng = zone.get('longitude')
                
                if lat is not None and lng is not None:
                    return float(lat), float(lng)
            
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.warning(f"Ошибка извлечения координат: {e}")
        
        return None, None
    
    def _extract_image_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлечение URL изображения"""
        # 1. Пробуем meta og:image (самый надежный)
        og_image = soup.find('meta', {'property': 'og:image'})
        if og_image and og_image.get('content'):
            return og_image['content']
        
        # 2. Ищем первое крупное изображение в контенте
        # Ищем в области заголовка/героя
        hero_images = soup.select('h1 + * img, .hero img, .featured img')
        for img in hero_images:
            src = img.get('src') or img.get('data-src')
            if src:
                return urljoin(self.base_url, src)
        
        # 3. Fallback: первое изображение в статье
        article_img = soup.select_one('article img, main img')
        if article_img:
            src = article_img.get('src') or article_img.get('data-src')
            if src:
                return urljoin(self.base_url, src)
        
        return None
    
    def parse_places_from_list(self, list_url: str) -> List[Dict]:
        """
        Полный пайплайн: парсинг списка + детальных страниц
        Возвращает список полных данных о местах
        """
        logger.info(f"Начинаем парсинг списка: {list_url}")
        
        # 1. Парсим страницу списка
        list_places = self.parse_list_page(list_url)
        if not list_places:
            logger.warning("Не найдено мест на странице списка")
            return []
        
        # 2. Парсим каждую детальную страницу
        full_places = []
        for i, place_info in enumerate(list_places, 1):
            logger.info(f"Парсинг места {i}/{len(list_places)}: {place_info['title']}")
            
            detail_data = self.parse_detail_page(place_info['detail_url'])
            if detail_data:
                # Объединяем данные из списка и детальной страницы
                detail_data.update({
                    'teaser': place_info.get('teaser'),
                    'address_fallback': place_info.get('address_fallback'),
                    'hours_fallback': place_info.get('hours_fallback'),
                    'list_number': place_info.get('number')
                })
                full_places.append(detail_data)
            else:
                logger.warning(f"Не удалось получить детальные данные для {place_info['title']}")
        
        logger.info(f"Успешно спарсено {len(full_places)} мест")
        return full_places
    
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
            if any(social in href.lower() for social in ['facebook', 'twitter', 'pinterest', 'share']):
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
                import json
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


def test_parser():
    """Тестовая функция для проверки парсера"""
    adapter = TimeOutAdapter()
    
    # Тестируем на реальной странице
    test_url = "https://www.timeout.com/bangkok/restaurants/bangkoks-best-new-cafes-of-2025"
    
    print("Тестируем парсер TimeOut Bangkok...")
    print(f"URL: {test_url}")
    
    # Парсим список
    places = adapter.parse_places_from_list(test_url)
    
    print(f"\nНайдено мест: {len(places)}")
    
    for i, place in enumerate(places[:3], 1):  # Показываем первые 3
        print(f"\n--- Место {i} ---")
        print(f"Название: {place.get('name')}")
        print(f"Категория: {place.get('category')}")
        print(f"Район: {place.get('area')}")
        print(f"Адрес: {place.get('address')}")
        print(f"Часы: {place.get('hours_text')}")
        print(f"Google Maps: {place.get('gmaps_url')}")
        print(f"Картинка: {place.get('picture_url')}")
        print(f"Описание: {place.get('description_full', '')[:100]}...")
    
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
            if any(social in href.lower() for social in ['facebook', 'twitter', 'pinterest', 'share']):
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
                import json
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


if __name__ == "__main__":
    test_parser()
