#!/usr/bin/env python3
"""
AI Editor Agent - финальный этап обработки данных
Проверяет достоверность, ищет качественные изображения и дополняет недостающие поля
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

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from apps.core.db import SessionLocal
from apps.places.models import Place
from openai import OpenAI
from .web_verifier import WebVerifier
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AIEditorAgent:
    """
    AI Editor Agent - проверяет и дополняет данные мест
    """
    
    def __init__(self, api_key: str = None, batch_size: int = 5):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.batch_size = batch_size
        self.client = OpenAI(api_key=self.api_key)
        self.web_verifier = WebVerifier()
        
        # Статистика
        self.processed_count = 0
        self.verified_count = 0
        self.updated_count = 0
        self.error_count = 0
    
    def run(self):
        """Основной цикл работы агента"""
        logger.info("🚀 Запуск AI Editor Agent...")
        
        try:
            self._process_batches()
            
            logger.info("✅ AI Editor Agent завершил работу!")
            self._print_stats()
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            raise
    
    def _process_batches(self):
        """Обработка записей батчами"""
        db = SessionLocal()
        try:
            while True:
                # Получаем места для финальной проверки (published или new)
                places = db.query(Place).filter(
                    Place.processing_status.in_(['published', 'new'])
                ).filter(
                    Place.ai_verified.is_(None)  # Еще не проверены AI-агентом
                ).limit(self.batch_size).all()
                
                if not places:
                    logger.info("Нет записей для проверки AI-агентом")
                    break
                
                logger.info(f"Проверяем батч из {len(places)} записей")
                
                for place in places:
                    try:
                        self._process_place(place, db)
                    except Exception as e:
                        logger.error(f"Ошибка обработки места {place.id}: {e}")
                        self.error_count += 1
                        self._mark_as_error(place, str(e), db)
                
                db.commit()
                self.processed_count += len(places)
                
        finally:
            db.close()
    
    def _process_place(self, place: Place, db: Session):
        """Обработка одного места AI-агентом"""
        logger.info(f"🔍 Проверяем место: {place.name}")
        
        # 1. Проверяем достоверность данных (имя, теги, описание)
        verification_result = self._verify_place_data(place)
        
        # 2. Если данные неверные, ищем достоверные через веб-поиск
        correction_result = None
        if not verification_result.get("data_accurate", True):
            logger.info(f"🔧 Данные места {place.name} неточные, ищем достоверные...")
            correction_result = self._search_correct_data(place)
            
            # Если нашли лучшие данные, обновляем место
            if correction_result and correction_result.get("found_better_data"):
                self._apply_data_corrections(place, correction_result, db)
                # Запускаем саммаризатор для пересоздания summary и тегов
                self._trigger_resummarize(place, db)
        
        # 3. Ищем качественные изображения
        image_result = self._find_quality_images(place)
        
        # 4. Проверяем и дополняем недостающие поля
        completion_result = self._complete_missing_fields(place)
        
        # 5. Обновляем запись
        self._update_place(place, verification_result, image_result, completion_result, correction_result, db)
        
        self.verified_count += 1
        logger.info(f"✅ Место {place.id} обработано")
    
    def _verify_place_data(self, place: Place) -> Dict[str, Any]:
        """Проверка достоверности данных места (имя, теги, описание)"""
        try:
            # Используем GPT для анализа точности данных
            gpt_verification = self._gpt_verify_place_data(place)
            
            # Определяем, нужно ли искать более точные данные
            data_accurate = (
                gpt_verification.get("name_correct", True) and
                gpt_verification.get("description_correct", True) and
                gpt_verification.get("tags_correct", True)
            )
            
            # Возвращаем результаты
            return {
                "gpt_verification": gpt_verification,
                "data_accurate": data_accurate,
                "issues": gpt_verification.get("issues", []),
                "suggestions": gpt_verification.get("suggestions", [])
            }
            
        except Exception as e:
            logger.error(f"Ошибка верификации места {place.id}: {e}")
            return {
                "web_verification": None,
                "gpt_verification": None,
                "overall_verification": "error",
                "issues": [f"Ошибка верификации: {e}"],
                "suggestions": []
            }
    
    def _gpt_verify_place_data(self, place: Place) -> Dict[str, Any]:
        """Проверка достоверности данных места через GPT"""
        try:
            # Расширенный промпт для проверки всех полей
            prompt = f"""Analyze this restaurant data for accuracy:

Name: {place.name}
Category: {place.category}
Description: {place.description_full or place.summary or 'No description'}
Tags: {place.tags_csv or 'No tags'}

Check if:
1. Name is correct and properly formatted
2. Description is accurate and informative
3. Tags are relevant and appropriate
4. Category matches the place type

Answer with JSON: {{
    "name_correct": true/false,
    "description_correct": true/false, 
    "tags_correct": true/false,
    "category_correct": true/false,
    "issues": ["list of specific issues found"],
    "suggestions": ["suggestions for improvement"]
}}"""
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200
            )
            
            # Проверяем, что ответ не пустой
            response_text = response.choices[0].message.content.strip()
            if not response_text:
                logger.warning("GPT вернул пустой ответ")
                return self._get_default_verification_result()
            
            # Безопасный парсинг JSON
            try:
                result = self._parse_gpt_json_response(response_text)
                if result is None:
                    return self._get_default_verification_result()
                # Валидируем структуру
                required_keys = ["name_correct", "category_correct", "description_correct"]
                if not all(key in result for key in required_keys):
                    logger.warning("GPT вернул неполную структуру JSON")
                    return self._get_default_verification_result()
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"Ошибка парсинга GPT ответа: {e}")
                logger.warning(f"Ответ GPT: {response_text[:100]}...")
                return self._get_default_verification_result()
            
        except Exception as e:
            logger.error(f"Ошибка GPT верификации места {place.id}: {e}")
            return self._get_default_verification_result()
    
    def _parse_gpt_json_response(self, response_text: str) -> Dict[str, Any]:
        """Парсинг GPT ответа с поддержкой markdown формата"""
        try:
            # Убираем markdown обертку если есть
            if "```json" in response_text:
                # Извлекаем JSON из markdown блока
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                if end != -1:
                    json_text = response_text[start:end].strip()
                else:
                    json_text = response_text[start:].strip()
            elif "```" in response_text:
                # Извлекаем JSON из обычного блока
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                if end != -1:
                    json_text = response_text[start:end].strip()
                else:
                    json_text = response_text[start:].strip()
            else:
                json_text = response_text.strip()
            
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.warning(f"Ошибка парсинга JSON: {e}")
            logger.warning(f"Исходный текст: {response_text[:200]}...")
            return None

    def _check_if_needs_resummarize(self, place: Place) -> bool:
        """Проверяет, нужно ли отправить место в саммаризатор для обновления тегов"""
        # Проверяем, есть ли новые теги по кухне, типу места и т.д.
        if not place.tags_csv:
            return True
        
        tags = place.tags_csv.lower()
        
        # Проверяем наличие тегов кухни
        cuisine_tags = ['thai', 'italian', 'japanese', 'chinese', 'indian', 'french', 'korean', 'vietnamese', 'mexican', 'mediterranean', 'guangdong', 'european']
        has_cuisine = any(cuisine in tags for cuisine in cuisine_tags)
        
        # Проверяем наличие тегов стиля
        style_tags = ['fine_dining', 'casual', 'street_food', 'rooftop', 'speakeasy', 'luxury', 'traditional', 'modern', 'vegetarian', 'sustainable']
        has_style = any(style in tags for style in style_tags)
        
        # Проверяем наличие тегов атмосферы
        atmosphere_tags = ['intimate', 'energetic', 'upscale', 'cozy', 'minimalist', 'creative', 'family_friendly', 'adult', 'chill', 'community']
        has_atmosphere = any(atmosphere in tags for atmosphere in atmosphere_tags)
        
        # Проверяем наличие специфичных тегов для ресторанов
        restaurant_specific = ['brunch', 'desserts', 'noodles', 'craft_coffee', 'specialty_coffee', 'streetwear', 'trendy']
        has_restaurant_specific = any(specific in tags for specific in restaurant_specific)
        
        # Если нет специфичных тегов, отправляем в саммаризатор
        if not (has_cuisine or has_style or has_atmosphere or has_restaurant_specific):
            logger.info(f"Место {place.name} нуждается в обновлении тегов (нет специфичных тегов)")
            return True
        
        # Дополнительная проверка: если у ресторана нет тегов кухни, отправляем в саммаризатор
        if place.category and 'restaurant' in place.category.lower() and not has_cuisine:
            logger.info(f"Ресторан {place.name} нуждается в тегах кухни")
            return True
        
        return False

    def _get_default_verification_result(self) -> Dict[str, Any]:
        """Возвращает дефолтный результат верификации"""
        return {
            "name_correct": True,
            "category_correct": True,
            "description_correct": True,
            "tags_correct": True,
            "issues": [],
            "suggestions": []
        }
    
    def _search_correct_data(self, place: Place) -> Dict[str, Any]:
        """Поиск достоверных данных через веб-поиск"""
        try:
            logger.info(f"🔍 Ищем достоверные данные для {place.name}")
            
            # Используем веб-верификатор для поиска точных данных
            web_data = self.web_verifier.verify_place_data(
                place.name,
                place.category,
                place.address
            )
            
            if web_data and web_data.get("verified"):
                # Если веб-поиск нашел достоверные данные
                return {
                    "found_better_data": True,
                    "source": "web_search",
                    "corrected_name": web_data.get("corrected_name", place.name),
                    "corrected_description": web_data.get("corrected_description"),
                    "corrected_tags": web_data.get("corrected_tags"),
                    "confidence": web_data.get("confidence", 0.8),
                    "sources": web_data.get("sources", [])
                }
            else:
                # Если веб-поиск не помог, используем GPT для улучшения
                return self._gpt_improve_data(place)
                
        except Exception as e:
            logger.error(f"Ошибка поиска достоверных данных для {place.name}: {e}")
            return self._gpt_improve_data(place)
    
    def _gpt_improve_data(self, place: Place) -> Dict[str, Any]:
        """Улучшение данных через GPT на основе существующей информации"""
        try:
            prompt = f"""Improve this restaurant data based on common knowledge:

Current Name: {place.name}
Current Category: {place.category}
Current Description: {place.description_full or place.summary or 'No description'}
Current Tags: {place.tags_csv or 'No tags'}

Provide improved, more accurate data:

Answer with JSON: {{
    "corrected_name": "improved name",
    "corrected_description": "better description",
    "corrected_tags": "improved,tags,list",
    "improvements_made": ["list of improvements"],
    "confidence": 0.8
}}"""
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500
            )
            
            response_text = response.choices[0].message.content.strip()
            if not response_text:
                return {"found_better_data": False}
            
            try:
                result = self._parse_gpt_json_response(response_text)
                if result is None:
                    return self._get_default_verification_result()
                result["found_better_data"] = True
                result["source"] = "gpt_improvement"
                return result
            except json.JSONDecodeError:
                return {"found_better_data": False}
                
        except Exception as e:
            logger.error(f"Ошибка GPT улучшения данных для {place.name}: {e}")
            return {"found_better_data": False}
    
    def _apply_data_corrections(self, place: Place, correction_result: Dict[str, Any], db: Session):
        """Применение исправлений к данным места"""
        try:
            updated = False
            
            # Обновляем название если найдено лучшее
            if correction_result.get("corrected_name") and correction_result["corrected_name"] != place.name:
                logger.info(f"Исправляем название: {place.name} -> {correction_result['corrected_name']}")
                place.name = correction_result["corrected_name"]
                updated = True
            
            # Обновляем описание если найдено лучшее
            if correction_result.get("corrected_description"):
                logger.info(f"Исправляем описание для {place.name}")
                place.description_full = correction_result["corrected_description"]
                updated = True
            
            # Обновляем теги если найдены лучшие
            if correction_result.get("corrected_tags"):
                logger.info(f"Исправляем теги для {place.name}")
                place.tags_csv = correction_result["corrected_tags"]
                updated = True
            
            if updated:
                # Сбрасываем только summary, чтобы саммаризатор его пересоздал
                # tags_csv оставляем обновленным
                place.summary = None
                place.processing_status = 'new'  # Возвращаем в статус для переобработки
                place.updated_at = datetime.now()
                logger.info(f"✅ Данные места {place.name} исправлены и отправлены на переобработку")
            
        except Exception as e:
            logger.error(f"Ошибка применения исправлений для {place.name}: {e}")
    
    def _trigger_resummarize(self, place: Place, db: Session):
        """Запуск саммаризатора для пересоздания summary и тегов"""
        try:
            # Логируем, что место отправлено на переобработку
            logger.info(f"🔄 Место {place.name} отправлено на переобработку саммаризатором")
            
            # В реальной системе здесь можно добавить:
            # - Отправку в очередь задач (Celery/RQ)
            # - Вызов API саммаризатора
            # - Или просто изменение статуса (что мы уже сделали)
            
        except Exception as e:
            logger.error(f"Ошибка запуска саммаризатора для {place.name}: {e}")
    
    def _get_default_completion_result(self, place: Place) -> Dict[str, Any]:
        """Возвращает дефолтный результат дополнения полей"""
        # Умные fallback значения на основе категории
        category = place.category.lower() if place.category else ""
        
        if "bar" in category or "nightclub" in category:
            tags = "bar,nightlife,drinks"
            price_level = 3
        elif "restaurant" in category or "cafe" in category:
            tags = "restaurant,food,dining"
            price_level = 2
        elif "entertainment" in category:
            tags = "entertainment,fun,activity"
            price_level = 2
        else:
            tags = "restaurant,food,thai"
            price_level = 2
        
        return {
            "description": place.description_full or place.summary or "Описание недоступно",
            "tags": tags,
            "hours": {},
            "price_level": price_level
        }
    
    def _find_quality_images(self, place: Place) -> Dict[str, Any]:
        """Поиск качественных изображений места"""
        try:
            # Если уже есть изображение, не ищем новое
            if place.picture_url and place.picture_url.strip():
                logger.info(f"У места {place.name} уже есть изображение: {place.picture_url[:50]}...")
                return {
                    "found": True,
                    "url": place.picture_url,
                    "source": "existing",
                    "quality": "existing"
                }
            
            # Поиск реальных изображений места только если поле пустое
            logger.info(f"У места {place.name} нет изображения, ищем новое...")
            image_url = self._search_real_place_images(place)
            
            if image_url:
                # Определяем источник изображения
                if "unsplash.com" in image_url:
                    source = "placeholder"
                    quality = "placeholder"
                else:
                    source = "real_search"
                    quality = "real"
                
                return {
                    "found": True,
                    "url": image_url,
                    "source": source,
                    "quality": quality
                }
            
            return {
                "found": False,
                "url": None,
                "source": None,
                "quality": None
            }
            
        except Exception as e:
            logger.error(f"Ошибка поиска изображений для места {place.id}: {e}")
            return {
                "found": False,
                "url": None,
                "source": "error",
                "quality": None
            }
    
    def _search_real_place_images(self, place: Place) -> str:
        """Поиск новых фотографий для места (вызывается только если picture_url пустое)"""
        try:
            # Пробуем найти через Google Places API
            if place.gmaps_place_id:
                google_photos = self._get_google_place_photos(place.gmaps_place_id, place)
                if google_photos:
                    logger.info(f"Найдены фотографии через Google Places API для {place.name}")
                    return google_photos
            
            # Если ничего не нашли, используем fallback
            logger.warning(f"Не найдены качественные фотографии для {place.name}")
            return self._get_fallback_image(place)
            
        except Exception as e:
            logger.warning(f"Ошибка поиска реальных изображений для {place.name}: {e}")
            return self._get_fallback_image(place)
    
    def _search_google_images(self, place: Place) -> str:
        """Поиск через Google Custom Search API"""
        try:
            search_query = f"{place.name} {place.category} Bangkok Thailand"
            
            # Формируем запрос к Google Custom Search API
            api_key = os.getenv('GOOGLE_API_KEY', 'AIzaSyBjExK9M7wOu929zQNbnlFJ8kjr-QreP6w')
            search_engine_id = os.getenv('GOOGLE_SEARCH_ENGINE_ID', 'your_search_engine_id')
            
            if not search_engine_id or search_engine_id == 'your_search_engine_id':
                return None
            
            # Запрос к Google Custom Search API
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': api_key,
                'cx': search_engine_id,
                'q': search_query,
                'searchType': 'image',
                'num': 5,
                'imgSize': 'medium',
                'imgType': 'photo',
                'safe': 'medium'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'items' in data and data['items']:
                # Выбираем лучшее изображение
                for item in data['items']:
                    image_url = item.get('link', '')
                    if self._is_quality_real_image(image_url, place):
                        logger.info(f"Найдено реальное изображение через Google для {place.name}")
                        return image_url
                
                # Если не нашли качественное, берем первое
                first_image = data['items'][0].get('link', '')
                logger.info(f"Используем первое найденное изображение через Google для {place.name}")
                return first_image
            
            return None
            
        except Exception as e:
            logger.warning(f"Ошибка Google Custom Search для {place.name}: {e}")
            return None
    
    def _search_duckduckgo_images(self, place: Place) -> str:
        """Поиск через DuckDuckGo (без API)"""
        try:
            search_query = f"{place.name} {place.category} Bangkok"
            
            # Используем DuckDuckGo для поиска изображений
            search_url = "https://duckduckgo.com/"
            params = {
                'q': search_query,
                'iax': 'images',
                'ia': 'images'
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(search_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Простой парсинг HTML для извлечения URL изображений
            import re
            img_pattern = r'https://[^"\s]+\.(?:jpg|jpeg|png|webp)(?:\?[^"\s]*)?'
            matches = re.findall(img_pattern, response.text, re.IGNORECASE)
            
            # Фильтруем качественные изображения
            for url in matches[:10]:
                if self._is_quality_real_image(url, place):
                    logger.info(f"Найдено реальное изображение через DuckDuckGo для {place.name}")
                    return url
            
            return None
            
        except Exception as e:
            logger.warning(f"Ошибка DuckDuckGo поиска для {place.name}: {e}")
            return None
    
    def _is_quality_real_image(self, url: str, place: Place) -> bool:
        """Проверяет качество реального изображения"""
        try:
            # Проверяем, что URL валидный
            if not url or not url.startswith('http'):
                return False
            
            # Исключаем социальные сети и аватары
            excluded_domains = ['facebook.com', 'instagram.com', 'twitter.com', 'linkedin.com', 'pinterest.com']
            if any(domain in url.lower() for domain in excluded_domains):
                return False
            
            # Предпочитаем изображения с высоким разрешением
            if any(param in url.lower() for param in ['w=800', 'w=1200', 'w=1600', 'width=800', 'width=1200']):
                return True
            
            # Проверяем расширение
            if any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                return True
            
            return True
            
        except Exception:
            return False
    
    def _get_fallback_image(self, place: Place) -> str:
        """Возвращает fallback изображение на основе категории"""
        # Простые placeholder изображения по категориям
        placeholders = {
            "restaurant": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=400",
            "bar": "https://images.unsplash.com/photo-1514933651103-005eec06c04b?w=400",
            "cafe": "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=400",
            "entertainment": "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=400"
        }
        
        category = place.category.lower() if place.category else ""
        
        for key, url in placeholders.items():
            if key in category:
                return url
        
        # Дефолтное изображение
        return "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=400"
    
    def _get_google_place_photos(self, place_id: str, place: Place = None) -> str:
        """Получение фотографий места через новый Google Places API"""
        try:
            api_key = os.getenv('GOOGLE_MAPS_API_KEY', 'AIzaSyBjExK9M7wOu929zQNbnlFJ8kjr-QreP6w')
            
            # Используем новый Places API
            url = f"https://places.googleapis.com/v1/places/{place_id}"
            headers = {
                'Content-Type': 'application/json',
                'X-Goog-Api-Key': api_key,
                'X-Goog-FieldMask': 'photos'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'photos' in data:
                photos = data['photos']
                
                if photos:
                    # Выбираем лучшее фото с интерьером или едой
                    best_photo = self._select_best_photo(photos, place)
                    if best_photo:
                        photo_name = best_photo['name']
                        
                        # Получаем URL фотографии
                        photo_url = self._get_google_photo_url_new(photo_name, api_key)
                        
                        if photo_url:
                            logger.info(f"Получена фотография Google Places: {photo_url[:50]}...")
                            return photo_url
            
            return None
            
        except Exception as e:
            logger.warning(f"Ошибка получения фотографий Google Places: {e}")
            return None
    
    def _get_google_photo_url_new(self, photo_name: str, api_key: str) -> str:
        """Получение URL фотографии через новый Google Places API"""
        try:
            # Используем новый Places API для получения фотографии
            url = f"https://places.googleapis.com/v1/{photo_name}/media"
            params = {
                'maxWidthPx': 800,  # Высокое качество
                'key': api_key
            }
            
            response = requests.get(url, params=params, allow_redirects=False, timeout=10)
            
            if response.status_code == 302:  # Redirect
                return response.headers.get('Location', '')
            elif response.status_code == 200:
                # Если возвращается изображение напрямую
                return url + '?' + '&'.join([f'{k}={v}' for k, v in params.items()])
            
            return None
            
        except Exception as e:
            logger.warning(f"Ошибка получения URL фотографии: {e}")
            return None
    
    def _get_google_photo_url(self, photo_reference: str, api_key: str) -> str:
        """Получение URL фотографии по photo_reference (старый API)"""
        try:
            url = "https://maps.googleapis.com/maps/api/place/photo"
            params = {
                'photo_reference': photo_reference,
                'maxwidth': 800,  # Высокое качество
                'key': api_key
            }
            
            # Делаем запрос для получения URL
            response = requests.get(url, params=params, allow_redirects=False, timeout=10)
            
            if response.status_code == 302:  # Redirect
                return response.headers.get('Location', '')
            elif response.status_code == 200:
                # Если возвращается изображение напрямую
                return url + '?' + '&'.join([f'{k}={v}' for k, v in params.items()])
            
            return None
            
        except Exception as e:
            logger.warning(f"Ошибка получения URL фотографии: {e}")
            return None
    
    def _find_google_place_id(self, place: Place) -> str:
        """Поиск Google Place ID для места"""
        try:
            api_key = os.getenv('GOOGLE_MAPS_API_KEY', 'AIzaSyBjExK9M7wOu929zQNbnlFJ8kjr-QreP6w')
            
            # Используем Text Search для поиска места
            url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            params = {
                'query': f"{place.name} {place.category} Bangkok",
                'location': f"{place.lat},{place.lng}",
                'radius': 1000,  # 1км радиус
                'key': api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') == 'OK' and 'results' in data:
                results = data['results']
                
                if results:
                    # Берем первое найденное место
                    place_id = results[0].get('place_id')
                    logger.info(f"Найден Google Place ID для {place.name}: {place_id}")
                    return place_id
            
            return None
            
        except Exception as e:
            logger.warning(f"Ошибка поиска Google Place ID для {place.name}: {e}")
            return None
    
    def _select_best_photo(self, photos: list, place: Place) -> dict:
        """Выбор лучшей фотографии с интерьером или едой"""
        try:
            if not photos:
                return None
            
            # Ключевые слова для поиска фотографий с интерьером и едой
            interior_keywords = [
                'interior', 'inside', 'dining', 'seating', 'table', 'chair', 
                'restaurant', 'cafe', 'bar', 'kitchen', 'counter', 'decor',
                'atmosphere', 'ambiance', 'space', 'room', 'hall'
            ]
            
            food_keywords = [
                'food', 'dish', 'meal', 'plate', 'drink', 'coffee', 'tea',
                'cocktail', 'beer', 'wine', 'dessert', 'cake', 'pasta',
                'pizza', 'sushi', 'thai', 'cuisine', 'menu', 'serving'
            ]
            
            # Сортируем фотографии по приоритету
            scored_photos = []
            
            for photo in photos:
                score = 0
                photo_info = photo.get('authorAttributions', [{}])[0]
                display_name = photo_info.get('displayName', '').lower()
                
                # Проверяем размеры (предпочитаем большие фотографии)
                width = photo.get('widthPx', 0)
                height = photo.get('heightPx', 0)
                if width >= 1000 and height >= 1000:
                    score += 10
                elif width >= 800 and height >= 800:
                    score += 5
                
                # Проверяем ключевые слова в имени автора (часто указывает на тип фото)
                for keyword in interior_keywords:
                    if keyword in display_name:
                        score += 15
                        break
                
                for keyword in food_keywords:
                    if keyword in display_name:
                        score += 20  # Еда имеет приоритет
                        break
                
                # Проверяем, что это не внешний вид здания
                if any(word in display_name for word in ['exterior', 'outside', 'building', 'facade', 'street']):
                    score -= 10
                
                # Предпочитаем фотографии от владельца заведения
                if place and place.name and place.name.lower() in display_name:
                    score += 25
                
                scored_photos.append((score, photo))
            
            # Сортируем по убыванию счета
            scored_photos.sort(key=lambda x: x[0], reverse=True)
            
            # Возвращаем лучшую фотографию
            if scored_photos:
                best_score, best_photo = scored_photos[0]
                logger.info(f"Выбрана фотография со счетом {best_score} для {place.name}")
                return best_photo
            
            # Если ничего не подошло, возвращаем первую
            return photos[0]
            
        except Exception as e:
            logger.warning(f"Ошибка выбора лучшей фотографии: {e}")
            return photos[0] if photos else None
    
    
    def _is_quality_image(self, url: str) -> bool:
        """Проверка качества изображения"""
        try:
            # Простая проверка по URL
            if not url or not url.startswith('http'):
                return False
            
            # Проверяем расширение
            quality_extensions = ['.jpg', '.jpeg', '.png', '.webp']
            if not any(url.lower().endswith(ext) for ext in quality_extensions):
                return False
            
            # Проверяем размер (по URL параметрам)
            if 'w=' in url or 'width=' in url:
                return True
            
            return True
            
        except Exception:
            return False
    
    def _select_best_image(self, urls: List[str], place: Place) -> Optional[str]:
        """Выбор лучшего изображения из найденных"""
        if not urls:
            return None
        
        # Простая эвристика выбора
        for url in urls:
            if self._is_quality_image(url):
                return url
        
        return urls[0] if urls else None
    
    def _complete_missing_fields(self, place: Place) -> Dict[str, Any]:
        """Дополнение недостающих полей"""
        try:
            missing_fields = []
            suggestions = {}
            
            # Проверяем основные поля
            if not place.description_full and not place.summary:
                missing_fields.append("description")
            
            if not place.tags_csv:
                missing_fields.append("tags")
            
            if not place.hours_json:
                missing_fields.append("hours")
            
            if not place.price_level:
                missing_fields.append("price_level")
            
            if missing_fields:
                # Простой промпт для дополнения полей
                prompt = f"""Add missing data for restaurant:

Name: {place.name}
Category: {place.category}

Missing: {', '.join(missing_fields)}

Return JSON: {{"price_level": 2, "tags": "restaurant,food"}}"""
                
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=300
                )
                
                # Проверяем, что ответ не пустой
                response_text = response.choices[0].message.content.strip()
                if not response_text:
                    logger.warning("GPT вернул пустой ответ для дополнения полей")
                    result = self._get_default_completion_result(place)
                else:
                    # Безопасный парсинг JSON
                    try:
                        result = self._parse_gpt_json_response(response_text)
                        if result is None:
                            return self._get_default_verification_result()
                        # Валидируем структуру
                        if not isinstance(result, dict):
                            raise ValueError("Result is not a dictionary")
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning(f"Ошибка парсинга GPT ответа для дополнения полей: {e}")
                        logger.warning(f"Ответ GPT: {response_text[:100]}...")
                        result = self._get_default_completion_result(place)
            else:
                result = {}
                return {
                    "missing_fields": missing_fields,
                    "completions": result,
                    "success": True
                }
            
            return {
                "missing_fields": [],
                "completions": {},
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Ошибка дополнения полей для места {place.id}: {e}")
            return {
                "missing_fields": [],
                "completions": {},
                "success": False,
                "error": str(e)
            }
    
    def _update_place(self, place: Place, verification: Dict, image: Dict, completion: Dict, correction: Dict, db: Session):
        """Обновление места на основе результатов AI-анализа"""
        try:
            updated = False
            
            # Обновляем верификацию
            place.ai_verified = True
            place.ai_verification_date = datetime.now()
            
            # Обрабатываем результаты исправлений данных
            if correction and correction.get("found_better_data"):
                logger.info(f"📝 Применяем исправления данных для {place.name}")
                # Исправления уже применены в _apply_data_corrections
                # Здесь только логируем результат
                if correction.get("source") == "web_search":
                    logger.info(f"✅ Данные исправлены через веб-поиск (уверенность: {correction.get('confidence', 0)})")
                elif correction.get("source") == "gpt_improvement":
                    logger.info(f"✅ Данные улучшены через GPT (уверенность: {correction.get('confidence', 0)})")
            
            # Обновляем изображение только если у места его нет или найдено лучшее
            if image.get("found") and image.get("url"):
                # Обновляем только если у места нет изображения или найдено новое
                if not place.picture_url or place.picture_url.strip() == "":
                    place.picture_url = image["url"]
                    updated = True
                    logger.info(f"Добавлено изображение для {place.name}: {image['url'][:50]}...")
                elif image.get("url") != place.picture_url:
                    place.picture_url = image["url"]
                    updated = True
                    logger.info(f"Обновлено изображение для {place.name}: {image['url'][:50]}...")
                else:
                    logger.info(f"У места {place.name} уже есть изображение, пропускаем")
            
            # Дополняем недостающие поля
            if completion.get("success") and completion.get("completions"):
                comp = completion["completions"]
                
                if not place.description_full and comp.get("description"):
                    place.description_full = comp["description"]
                    updated = True
                
                if not place.tags_csv and comp.get("tags"):
                    place.tags_csv = comp["tags"]
                    updated = True
                
                if not place.hours_json and comp.get("hours"):
                    place.hours_json = json.dumps(comp["hours"])
                    updated = True
                
                if not place.price_level and comp.get("price_level"):
                    place.price_level = comp["price_level"]
                    updated = True
            
            # Проверяем, нужно ли обновить теги через саммаризатор
            needs_resummarize = self._check_if_needs_resummarize(place)
            if needs_resummarize:
                logger.info(f"🔄 Отправляем {place.name} в саммаризатор для обновления тегов")
                place.summary = None
                place.tags_csv = None
                place.processing_status = 'new'
                updated = True
            
            # Сохраняем результаты верификации
            verification_data = {
                "verification": verification,
                "image_search": image,
                "completion": completion,
                "data_correction": correction,
                "needs_resummarize": needs_resummarize,
                "processed_at": datetime.now().isoformat()
            }
            place.ai_verification_data = json.dumps(verification_data)
            
            # Устанавливаем статус published только после проверки AI Editor
            if not needs_resummarize:  # Если не отправляем в саммаризатор
                place.processing_status = 'published'
                place.published_at = datetime.now()
                logger.info(f"✅ Место {place.name} опубликовано")
                updated = True
            
            if updated:
                place.updated_at = datetime.now()
                self.updated_count += 1
                logger.info(f"Обновлено место: {place.name}")
            
        except Exception as e:
            logger.error(f"Ошибка обновления места {place.id}: {e}")
            raise
    
    def _mark_as_error(self, place: Place, error: str, db: Session):
        """Пометка места как ошибочного"""
        place.processing_status = 'error'
        place.last_error = error
        place.updated_at = datetime.now()
        db.add(place)
    
    def _print_stats(self):
        """Вывод статистики работы"""
        logger.info("📊 Статистика AI Editor Agent:")
        logger.info(f"  Обработано мест: {self.processed_count}")
        logger.info(f"  Проверено: {self.verified_count}")
        logger.info(f"  Обновлено: {self.updated_count}")
        logger.info(f"  Ошибок: {self.error_count}")


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='AI Editor Agent')
    parser.add_argument('--batch-size', type=int, default=5, help='Размер батча')
    parser.add_argument('--api-key', type=str, help='OpenAI API ключ')
    parser.add_argument('--verbose', '-v', action='store_true', help='Подробное логирование')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Установка API ключа
    if args.api_key:
        os.environ['OPENAI_API_KEY'] = args.api_key
    
    try:
        agent = AIEditorAgent(
            api_key=args.api_key,
            batch_size=args.batch_size
        )
        
        print("🤖 Запуск AI Editor Agent...")
        print(f"📊 Размер батча: {args.batch_size}")
        print(f"🔑 API ключ: {'установлен' if os.getenv('OPENAI_API_KEY') else 'НЕ НАЙДЕН'}")
        print("-" * 50)
        
        agent.run()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
