#!/usr/bin/env python3
"""
Enhanced AI Editor Agent - улучшенная версия с веб-скрапингом URL источников
Получает достоверные описания из источников и сжимает до главной сути
"""

import os
import sys
import json
import logging
import requests
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import time
import random
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote_plus

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.core.db import SessionLocal
from apps.places.models import Place
from openai import OpenAI
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EnhancedAIEditorAgent:
    """
    Enhanced AI Editor Agent - получает достоверные описания из URL источников
    """
    
    def __init__(self, api_key: str = None, batch_size: int = 10):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.batch_size = batch_size
        self.client = OpenAI(api_key=self.api_key)
        
        # Статистика
        self.processed_count = 0
        self.scraped_count = 0
        self.web_search_count = 0
        self.compressed_count = 0
        self.updated_count = 0
        self.error_count = 0
        
        # User-Agent для веб-скрапинга
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    
    def run(self):
        """Основной цикл работы агента"""
        logger.info("🚀 Starting Enhanced AI Editor Agent...")
        
        try:
            self._process_incomplete_places()
            
            logger.info("✅ Enhanced AI Editor Agent completed!")
            self._print_stats()
            
        except Exception as e:
            logger.error(f"❌ Critical error: {e}")
            raise
    
    def _process_incomplete_places(self):
        """Special processing for places without description and summary"""
        # Get places without description and summary
        db = SessionLocal()
        try:
            places = db.query(Place).filter(
                (Place.description_full.is_(None) | (Place.description_full == '')) &
                (Place.summary.is_(None) | (Place.summary == ''))
            ).limit(self.batch_size).all()
            
            if not places:
                logger.info("No places without description and summary to process")
                return
            
            logger.info(f"Found {len(places)} places without description and summary")
        finally:
            db.close()
        
        # Process each place individually with its own connection
        for place in places:
            try:
                self._process_incomplete_place_individual(place)
            except Exception as e:
                logger.error(f"Error processing place {place.id}: {e}")
                self.error_count += 1
        
        self.processed_count += len(places)
        logger.info(f"✅ Successfully processed {len(places)} places")
    
    def _process_incomplete_place_individual(self, place: Place):
        """Process one place without description and summary with individual connection"""
        logger.info(f"🔍 Processing place: {place.name}")
        
        description = None
        
        # 1. Check if there's a valid source URL
        if place.source_url and place.source_url.strip() and not place.source_url.startswith('timeout_'):
            logger.info(f"🌐 Found source URL: {place.source_url}")
            
            # 2. Try to get description from URL
            description = self._scrape_description_from_url(place.source_url, place)
            
            if description:
                logger.info(f"✅ Got description from URL ({len(description)} characters)")
                self.scraped_count += 1
            else:
                logger.warning(f"❌ Failed to get description from URL for {place.name}")
        
        # 3. If no description from URL, try web search
        if not description:
            logger.info(f"🔍 No valid URL, trying web search for: {place.name}")
            description = self._web_search_description(place)
            
            if description:
                logger.info(f"✅ Got description from web search ({len(description)} characters)")
                self.web_search_count += 1
            else:
                logger.warning(f"❌ Failed to get description from web search for {place.name}")
        
        # 4. If we have description, compress and update
        if description:
            # Compress description to main essence
            compressed_description = self._compress_description(description, place)
            
            if compressed_description:
                logger.info(f"📝 Compressed to {len(compressed_description)} characters")
                
                # Update place with individual connection
                self._update_place_individual(place, compressed_description)
                
                self.compressed_count += 1
                self.updated_count += 1
                
                logger.info(f"✅ Place {place.name} updated and sent for summarization")
            else:
                logger.warning(f"❌ Failed to compress description for {place.name}")
        else:
            logger.warning(f"❌ No description found for {place.name} from any source")
    
    def _update_place_individual(self, place: Place, description: str):
        """Update place with individual database connection"""
        db = SessionLocal()
        try:
            # Get fresh place from database
            db_place = db.query(Place).filter(Place.id == place.id).first()
            if db_place:
                db_place.description_full = description
                db_place.processing_status = 'new'  # Send for summarization
                db_place.updated_at = datetime.now()
                db.commit()
                logger.info(f"✅ Place {place.name} updated in database")
            else:
                logger.error(f"❌ Place {place.id} not found in database")
        except Exception as e:
            logger.error(f"❌ Database update error for place {place.id}: {e}")
            db.rollback()
            raise
        finally:
            db.close()
    
    def _scrape_description_from_url(self, url: str, place: Place) -> Optional[str]:
        """Получение описания с URL источника"""
        try:
            logger.info(f"🌐 Скрапинг URL: {url}")
            
            # Добавляем задержку между запросами
            time.sleep(random.uniform(1, 3))
            
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Определяем источник и извлекаем описание
            if 'timeout.com' in url:
                return self._extract_timeout_description(soup, place)
            elif 'bk.asia-city.com' in url:
                return self._extract_bk_magazine_description(soup, place)
            else:
                return self._extract_generic_description(soup, place)
                
        except Exception as e:
            logger.error(f"Ошибка скрапинга URL {url}: {e}")
            return None
    
    def _extract_timeout_description(self, soup: BeautifulSoup, place: Place) -> Optional[str]:
        """Извлечение описания с TimeOut"""
        try:
            # Ищем основные селекторы TimeOut
            selectors = [
                'div[data-testid="article-body"] p',
                '.article-body p',
                '.content p',
                'article p',
                '.description p',
                'div[class*="content"] p',
                'div[class*="article"] p'
            ]
            
            for selector in selectors:
                paragraphs = soup.select(selector)
                if paragraphs:
                    # Объединяем все параграфы
                    text = ' '.join([p.get_text(strip=True) for p in paragraphs])
                    if len(text) > 100:  # Минимальная длина
                        logger.info(f"Найдено описание TimeOut через селектор: {selector}")
                        return text
            
            # Fallback - ищем любой текст в статье
            article_text = soup.get_text()
            if len(article_text) > 200:
                logger.info("Используем fallback для TimeOut")
                return article_text
                
            return None
            
        except Exception as e:
            logger.error(f"Ошибка извлечения TimeOut описания: {e}")
            return None
    
    def _extract_bk_magazine_description(self, soup: BeautifulSoup, place: Place) -> Optional[str]:
        """Извлечение описания с BK Magazine"""
        try:
            # Ищем основные селекторы BK Magazine
            selectors = [
                '.entry-content p',
                '.post-content p',
                '.article-content p',
                '.content p',
                'article p',
                '.description p'
            ]
            
            for selector in selectors:
                paragraphs = soup.select(selector)
                if paragraphs:
                    # Объединяем все параграфы
                    text = ' '.join([p.get_text(strip=True) for p in paragraphs])
                    if len(text) > 100:  # Минимальная длина
                        logger.info(f"Найдено описание BK Magazine через селектор: {selector}")
                        return text
            
            # Fallback - ищем любой текст в статье
            article_text = soup.get_text()
            if len(article_text) > 200:
                logger.info("Используем fallback для BK Magazine")
                return article_text
                
            return None
            
        except Exception as e:
            logger.error(f"Ошибка извлечения BK Magazine описания: {e}")
            return None
    
    def _extract_generic_description(self, soup: BeautifulSoup, place: Place) -> Optional[str]:
        """Универсальное извлечение описания"""
        try:
            # Удаляем ненужные элементы
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()
            
            # Ищем основные селекторы
            selectors = [
                'article p',
                '.content p',
                '.description p',
                '.article p',
                'main p',
                'div[class*="content"] p',
                'div[class*="article"] p'
            ]
            
            for selector in selectors:
                paragraphs = soup.select(selector)
                if paragraphs:
                    text = ' '.join([p.get_text(strip=True) for p in paragraphs])
                    if len(text) > 100:
                        logger.info(f"Найдено описание через универсальный селектор: {selector}")
                        return text
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка универсального извлечения: {e}")
            return None
    
    def _web_search_description(self, place: Place) -> Optional[str]:
        """Поиск описания в интернете по названию места"""
        try:
            # Очищаем название от префиксов и лишних символов
            clean_name = self._clean_place_name(place.name)
            
            # Сначала пробуем известные сайты с ресторанами Бангкока
            known_sites = self._get_known_restaurant_sites(clean_name)
            
            for url, site_name in known_sites:
                try:
                    logger.info(f"🌐 Trying known site: {site_name} - {url}")
                    description = self._scrape_description_from_url(url, place)
                    
                    if description and len(description) > 100:
                        logger.info(f"✅ Found description from known site: {url}")
                        return description
                        
                except Exception as e:
                    logger.warning(f"Failed to scrape {url}: {e}")
                    continue
            
            # Если не нашли на известных сайтах, пробуем DuckDuckGo
            logger.info(f"🔍 Trying DuckDuckGo search for: {clean_name}")
            search_query = f"{clean_name} Bangkok restaurant bar cafe"
            
            # Добавляем задержку между запросами
            time.sleep(random.uniform(2, 4))
            
            # Выполняем поиск через DuckDuckGo
            search_url = f"https://duckduckgo.com/html/?q={quote_plus(search_query)}"
            
            response = requests.get(search_url, headers=self.headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Извлекаем ссылки из результатов поиска DuckDuckGo
            search_results = self._extract_duckduckgo_results(soup, place)
            
            if not search_results:
                logger.warning(f"No search results found for {place.name}")
                return None
            
            # Пробуем получить описание с каждой ссылки
            for url, title in search_results[:3]:  # Топ-3 результата
                try:
                    logger.info(f"🌐 Trying search result: {url}")
                    description = self._scrape_description_from_url(url, place)
                    
                    if description and len(description) > 100:
                        logger.info(f"✅ Found description from web search: {url}")
                        return description
                        
                except Exception as e:
                    logger.warning(f"Failed to scrape {url}: {e}")
                    continue
            
            logger.warning(f"No valid descriptions found from web search for {place.name}")
            return None
            
        except Exception as e:
            logger.error(f"Error in web search for {place.name}: {e}")
            return None
    
    def _get_known_restaurant_sites(self, clean_name: str) -> List[Tuple[str, str]]:
        """Получение известных сайтов с ресторанами Бангкока"""
        sites = []
        
        # TimeOut Bangkok
        timeout_url = f"https://www.timeout.com/bangkok/search?q={quote_plus(clean_name)}"
        sites.append((timeout_url, "TimeOut Bangkok"))
        
        # BK Magazine
        bk_url = f"https://bk.asia-city.com/search?q={quote_plus(clean_name)}"
        sites.append((bk_url, "BK Magazine"))
        
        # Google Maps (если есть координаты)
        # sites.append((f"https://www.google.com/maps/search/{quote_plus(clean_name)}+Bangkok", "Google Maps"))
        
        return sites
    
    def _clean_place_name(self, name: str) -> str:
        """Очистка названия места от префиксов и лишних символов"""
        # Убираем префиксы типа "1. ", "2. ", "10. "
        name = re.sub(r'^\d+\.\s*', '', name)
        
        # Убираем лишние пробелы
        name = name.strip()
        
        return name
    
    def _extract_duckduckgo_results(self, soup: BeautifulSoup, place: Place) -> List[Tuple[str, str]]:
        """Извлечение результатов поиска из DuckDuckGo"""
        try:
            results = []
            all_links = []
            
            # Ищем ссылки в результатах поиска DuckDuckGo
            for link in soup.find_all('a', class_='result__a'):
                href = link.get('href')
                title = link.get_text(strip=True)
                all_links.append((href, title))
                
                # Фильтруем только релевантные ссылки
                if (href and 
                    href.startswith('http') and 
                    not href.startswith('https://duckduckgo.com') and
                    not href.startswith('https://maps.') and
                    not href.startswith('https://translate.') and
                    title and len(title) > 10):
                    
                    # Проверяем релевантность по названию
                    if self._is_relevant_result(title, place.name):
                        results.append((href, title))
            
            # Если не нашли через класс, пробуем общий поиск
            if not results:
                logger.info(f"No results from result__a class, trying general search...")
                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    title = link.get_text(strip=True)
                    all_links.append((href, title))
                    
                    # Фильтруем только релевантные ссылки
                    if (href and 
                        href.startswith('http') and 
                        not href.startswith('https://duckduckgo.com') and
                        not href.startswith('https://maps.') and
                        not href.startswith('https://translate.') and
                        title and len(title) > 10):
                        
                        # Проверяем релевантность по названию
                        if self._is_relevant_result(title, place.name):
                            results.append((href, title))
            
            # Отладочная информация
            logger.info(f"Total links found: {len(all_links)}")
            logger.info(f"Valid HTTP links: {len([l for l in all_links if l[0] and l[0].startswith('http')])}")
            
            # Удаляем дубликаты
            seen = set()
            unique_results = []
            for url, title in results:
                if url not in seen:
                    seen.add(url)
                    unique_results.append((url, title))
            
            logger.info(f"Found {len(unique_results)} relevant DuckDuckGo search results")
            return unique_results
            
        except Exception as e:
            logger.error(f"Error extracting DuckDuckGo search results: {e}")
            return []
    
    def _is_relevant_result(self, title: str, place_name: str) -> bool:
        """Проверка релевантности результата поиска"""
        try:
            # Очищаем названия для сравнения
            clean_title = re.sub(r'[^\w\s]', '', title.lower())
            clean_place = re.sub(r'[^\w\s]', '', place_name.lower())
            
            # Убираем префиксы
            clean_place = re.sub(r'^\d+\.\s*', '', clean_place)
            
            # Разбиваем на слова
            title_words = set(clean_title.split())
            place_words = set(clean_place.split())
            
            # Проверяем пересечение ключевых слов
            common_words = title_words.intersection(place_words)
            
            # Более мягкие критерии релевантности
            is_relevant = (
                len(common_words) > 0 or  # Есть общие слова
                any(word in clean_title for word in clean_place.split() if len(word) > 3) or  # Есть длинные слова из названия
                clean_place in clean_title  # Название полностью содержится в заголовке
            ) and len(clean_title) > 15  # Заголовок не слишком короткий
            
            if is_relevant:
                logger.info(f"✅ Relevant result: '{title}' (common words: {common_words})")
            else:
                logger.debug(f"❌ Not relevant: '{title}' (common words: {common_words})")
            
            return is_relevant
            
        except Exception as e:
            logger.error(f"Error checking relevance: {e}")
            return False
    
    def _compress_description(self, description: str, place: Place) -> Optional[str]:
        """Сжатие описания до главной сути (6-10 предложений)"""
        try:
            if not description or len(description.strip()) < 50:
                return None
            
            # Очищаем текст
            cleaned_text = self._clean_text(description)
            
            # Если текст уже короткий, возвращаем как есть
            if len(cleaned_text) <= 500:
                return cleaned_text
            
            # Use GPT to compress to main essence
            prompt = f"""Compress this restaurant/place description to its main essence (6-10 sentences):

Name: {place.name}
Category: {place.category}

Original description:
{cleaned_text[:2000]}

Requirements:
- Keep only the most important information
- Maximum 6-10 sentences
- Focus on unique features, atmosphere, cuisine
- Remove repetitions and unnecessary details
- Preserve factual information

Compressed description:"""
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=300
            )
            
            compressed = response.choices[0].message.content.strip()
            
            if compressed and len(compressed) > 50:
                logger.info(f"Description compressed from {len(cleaned_text)} to {len(compressed)} characters")
                return compressed
            else:
                logger.warning("GPT returned too short compressed description")
                return cleaned_text[:500] + "..." if len(cleaned_text) > 500 else cleaned_text
                
        except Exception as e:
            logger.error(f"Error compressing description: {e}")
            # Fallback - just truncate to 500 characters
            return description[:500] + "..." if len(description) > 500 else description
    
    def _clean_text(self, text: str) -> str:
        """Clean text from unnecessary characters"""
        # Remove extra spaces and line breaks
        text = re.sub(r'\s+', ' ', text)
        # Remove HTML tags if any remain
        text = re.sub(r'<[^>]+>', '', text)
        # Remove unnecessary characters
        text = re.sub(r'[^\w\s.,!?;:-]', '', text)
        return text.strip()
    
    def _mark_as_error(self, place: Place, error: str, db: Session):
        """Mark place as erroneous"""
        place.processing_status = 'error'
        place.last_error = error
        place.updated_at = datetime.now()
        db.add(place)
    
    def _print_stats(self):
        """Print work statistics"""
        logger.info("📊 Enhanced AI Editor Agent Statistics:")
        logger.info(f"  Processed places: {self.processed_count}")
        logger.info(f"  Scraped descriptions: {self.scraped_count}")
        logger.info(f"  Web search descriptions: {self.web_search_count}")
        logger.info(f"  Compressed descriptions: {self.compressed_count}")
        logger.info(f"  Updated places: {self.updated_count}")
        logger.info(f"  Errors: {self.error_count}")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced AI Editor Agent')
    parser.add_argument('--batch-size', type=int, default=10, help='Batch size')
    parser.add_argument('--api-key', type=str, help='OpenAI API key')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Set API key
    if args.api_key:
        os.environ['OPENAI_API_KEY'] = args.api_key
    
    try:
        agent = EnhancedAIEditorAgent(
            api_key=args.api_key,
            batch_size=args.batch_size
        )
        
        print("🤖 Starting Enhanced AI Editor Agent...")
        print(f"📊 Batch size: {args.batch_size}")
        print(f"🔑 API key: {'set' if os.getenv('OPENAI_API_KEY') else 'NOT FOUND'}")
        print("-" * 50)
        
        agent.run()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
