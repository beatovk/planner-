#!/usr/bin/env python3
"""
Google Enricher Worker - обогащение данных через Google Places API
Итерация 3: Адаптеры поверх существующих воркеров
"""

import logging
from typing import Dict, Any, Optional
from apps.places.services.google_places import GooglePlaces, GooglePlacesError

logger = logging.getLogger(__name__)


class GoogleEnricherWorker:
    """Воркер для обогащения данных через Google Places API"""
    
    def __init__(self, api_key: Optional[str] = None, mock_mode: bool = False):
        self.google_places = GooglePlaces(api_key=api_key, mock_mode=mock_mode)
    
    def _search_place(self, place_name: str, place_address: str = None) -> Optional[Dict[str, Any]]:
        """Поиск места в Google Places API"""
        try:
            if not place_name or not place_name.strip():
                logger.warning("Нет названия места для поиска")
                return None
            
            # Нормализуем запрос
            query = place_name.strip()
            if place_address:
                query = f"{query} {place_address.strip()}"
            
            # Ищем место
            place_data = self.google_places.find_place(query)
            if not place_data:
                # Легаси fallback: получить place_id и детали через v2 JSON
                legacy_pid = self.google_places.legacy_find_place(query)
                if legacy_pid:
                    legacy_details = self.google_places.legacy_place_details(legacy_pid)
                    if legacy_details:
                        # Адаптируем к формату v1
                        result = {
                            "place_id": legacy_pid,
                            "coords": {
                                "lat": legacy_details.get('geometry', {}).get('location', {}).get('lat'),
                                "lng": legacy_details.get('geometry', {}).get('location', {}).get('lng'),
                            },
                            "maps_url": f"https://www.google.com/maps/place/?q=place_id:{legacy_pid}",
                            "address": legacy_details.get('formatted_address'),
                            "price_level": legacy_details.get('price_level'),
                            "business_status": None,
                            "utc_offset_minutes": None,
                            "opening_hours": legacy_details.get('opening_hours'),
                            "types": legacy_details.get('types', []),
                            "website": legacy_details.get('website'),
                            "phone": legacy_details.get('international_phone_number'),
                            "rating": legacy_details.get('rating'),
                            "user_rating_total": legacy_details.get('user_ratings_total'),
                        }
                        # Фото через legacy
                        photos = legacy_details.get('photos') or []
                        urls = []
                        for ph in photos[:5]:
                            ref = ph.get('photo_reference')
                            if ref:
                                url = self.google_places.legacy_photo_url(ref)
                                if url:
                                    urls.append(url)
                        if urls:
                            result['photos'] = urls
                        return result
            
            if not place_data:
                logger.warning(f"Место не найдено в Google: {place_name}")
                return None
            
            # Получаем детали места
            place_id = place_data.get("id")
            if not place_id:
                logger.warning(f"Нет place_id в ответе Google: {place_name}")
                return None
            
            details = self.google_places.place_details(place_id)
            if not details:
                logger.warning(f"Не удалось получить детали места: {place_id}")
                return None
            
            # Формируем результат
            result = {
                "place_id": place_id,
                "coords": {
                    "lat": details.get("location", {}).get("latitude"),
                    "lng": details.get("location", {}).get("longitude")
                },
                "maps_url": f"https://www.google.com/maps/place/?q=place_id:{place_id}",
                "address": details.get("formattedAddress"),
                "price_level": details.get("priceLevel"),
                "business_status": details.get("businessStatus"),
                "utc_offset_minutes": details.get("utcOffsetMinutes"),
                "opening_hours": details.get("regularOpeningHours"),
                "types": details.get("types", []),
                "website": details.get("websiteUri"),
                "phone": details.get("nationalPhoneNumber"),
                "rating": details.get("rating"),
                "user_rating_total": details.get("userRatingCount")
            }
            
            # Получаем фото (усиленный режим: формируем до 5 URL)
            photo_urls = []
            # 1) быстрый путь: единичное лучшее фото
            try:
                single = self.google_places.get_place_photos(place_id)
                if single:
                    photo_urls.append(single)
            except Exception:
                pass

            # 2) fallback: собрать несколько фото из details.photos
            try:
                photos = details.get("photos", []) or []
                if photos:
                    # сортировка по нашему скоу из селектора, если есть
                    scored = []
                    for ph in photos:
                        try:
                            # проставим score через селектор (он вернёт фото с _score)
                            _ = self.google_places._select_best_photo([ph])
                            scored.append((ph.get('_score', 0), ph))
                        except Exception:
                            scored.append((0, ph))
                    scored.sort(key=lambda x: x[0], reverse=True)
                    for _, ph in scored[:5]:
                        name = ph.get('name')
                        if not name:
                            continue
                        url = self.google_places._get_photo_url(name)
                        if url:
                            photo_urls.append(url)
                if photo_urls:
                    result["photos"] = list(dict.fromkeys(photo_urls))  # dedupe, keep order
            except Exception:
                pass
            
            logger.info(f"Успешно обогащено место: {place_name} -> {place_id}")
            return result
            
        except GooglePlacesError as e:
            logger.error(f"Ошибка Google Places API для {place_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при поиске места {place_name}: {e}")
            return None
    
    def enrich_place(self, place_data: Dict[str, Any]) -> Dict[str, Any]:
        """Обогатить данные места через Google Places API"""
        try:
            place_name = place_data.get("name", "")
            place_address = place_data.get("address", "")
            
            # Ищем место
            google_data = self._search_place(place_name, place_address)
            
            if not google_data:
                return {
                    "success": False,
                    "error": "Место не найдено в Google Places",
                    "google_data": {}
                }
            
            return {
                "success": True,
                "google_data": google_data,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Ошибка обогащения места: {e}")
            return {
                "success": False,
                "error": str(e),
                "google_data": {}
            }
