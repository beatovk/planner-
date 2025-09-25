#!/usr/bin/env python3
"""
Адаптер для Enricher агента (Google API)
Итерация 3: Адаптеры поверх существующих воркеров
"""

import json
from typing import Dict, Any
from apps.places.dto import PlaceDTO
from apps.places.shadow_utils import ShadowEventLogger
from apps.places.workers.google_enricher_worker import GoogleEnricherWorker


class EnricherAdapter:
    """Адаптер для Google Enricher"""
    
    def __init__(self):
        self.google_enricher = GoogleEnricherWorker(mock_mode=False)  # Используем реальные Google API данные
    
    def process(self, payload: PlaceDTO) -> PlaceDTO:
        """Обработать место через Enricher"""
        try:
            # Логируем начало обработки
            ShadowEventLogger.log_event(
                place_id=payload.place_id_internal,
                agent="enricher",
                code="PROCESSING_START",
                level="info",
                note="Начало обогащения через Google API"
            )
            
            # Увеличиваем счетчик попыток
            payload.increment_attempt("enricher")
            
            # Проверяем, есть ли уже Google данные (включая фото)
            if payload.google.get("place_id") and payload.google.get("coords", {}).get("lat") and payload.google.get("photos") and len(payload.google.get("photos", [])) > 0:
                # Логируем пропуск
                ShadowEventLogger.log_event(
                    place_id=payload.place_id_internal,
                    agent="enricher",
                    code="SKIP_EXISTING",
                    level="info",
                    note="Google данные (включая фото) уже существуют, пропускаем"
                )
                return payload
            
            # Подготавливаем данные для Google Enricher
            place_name = payload.clean.get("name", "").replace('\xa0', ' ').strip()
            # Убираем номера в начале названия (например, "6. Puckchumm" -> "Puckchumm")
            import re
            place_name = re.sub(r'^\d+\.\s*', '', place_name).strip()
            place_address = payload.clean.get("address", "")
            
            if not place_name:
                ShadowEventLogger.log_event(
                    place_id=payload.place_id_internal,
                    agent="enricher",
                    code="NO_NAME",
                    level="error",
                    note="Нет названия места для поиска в Google"
                )
                payload.add_diagnostic("enricher", "error", "NO_NAME", "Нет названия места")
                return payload
            
            # Вызываем Google Enricher
            place_data = {
                "name": place_name,
                "address": place_address
            }
            enrich_result = self.google_enricher.enrich_place(place_data)
            
            if enrich_result["success"]:
                result = enrich_result["google_data"]
            else:
                result = None
            
            if result and result.get("place_id"):
                # Обновляем Google данные
                payload.google["place_id"] = result["place_id"]
                if result.get("coords"):
                    payload.google["coords"] = result["coords"]
                if result.get("maps_url"):
                    payload.google["maps_url"] = result["maps_url"]
                if result.get("photos"):
                    payload.google["photos"] = result["photos"]
                
                # Обновляем дополнительные поля из Google API
                if result.get("address"):
                    payload.clean["address"] = result["address"]
                if result.get("price_level") is not None:
                    payload.clean["price_level"] = result["price_level"]
                if result.get("business_status"):
                    payload.clean["business_status"] = result["business_status"]
                if result.get("utc_offset_minutes") is not None:
                    payload.clean["utc_offset_minutes"] = result["utc_offset_minutes"]
                if result.get("opening_hours"):
                    payload.clean["hours_json"] = result["opening_hours"]
                if result.get("website"):
                    payload.clean["website"] = result["website"]
                if result.get("phone"):
                    payload.clean["phone"] = result["phone"]
                if result.get("rating") is not None:
                    payload.clean["rating"] = result["rating"]
                
                # Обновляем флаги качества
                if result.get("coords"):
                    payload.update_quality_flag("coords", "present")
                if result.get("photos"):
                    payload.update_quality_flag("photos", "ok")
                if result.get("address"):
                    payload.update_quality_flag("address", "present")
                if result.get("price_level") is not None:
                    payload.update_quality_flag("price_level", "present")
                
                # Логируем успех
                ShadowEventLogger.log_event(
                    place_id=payload.place_id_internal,
                    agent="enricher",
                    code="SUCCESS",
                    level="info",
                    note=f"Найдено место в Google: {result['place_id']}"
                )
                
                # Добавляем в историю
                payload.add_history("enricher", f"Обогащено через Google API")
                
                # Сохраняем изменения в базу данных (строгий режим: считаем успешным ENRICHED только при coords+photo)
                from apps.core.db import SessionLocal
                from apps.places.models import Place
                db = SessionLocal()
                try:
                    place = db.query(Place).get(payload.place_id_internal)
                    if place:
                        # Обновляем Google данные
                        if result.get("place_id"):
                            place.gmaps_place_id = result["place_id"]
                        if result.get("coords"):
                            place.lat = result["coords"].get("lat")
                            place.lng = result["coords"].get("lng")
                        if result.get("maps_url"):
                            place.gmaps_url = result["maps_url"]
                        if result.get("photos"):
                            photos = result["photos"]
                            place.picture_url = photos[0] if photos else None
                        
                        # Обновляем дополнительные поля
                        if result.get("address"):
                            place.address = result["address"]
                        if result.get("price_level") is not None:
                            # Конвертируем строку в число
                            price_level = result["price_level"]
                            if isinstance(price_level, str):
                                price_map = {
                                    "PRICE_LEVEL_FREE": 0,
                                    "PRICE_LEVEL_INEXPENSIVE": 1,
                                    "PRICE_LEVEL_MODERATE": 2,
                                    "PRICE_LEVEL_EXPENSIVE": 3,
                                    "PRICE_LEVEL_VERY_EXPENSIVE": 4
                                }
                                place.price_level = price_map.get(price_level, 2)
                            else:
                                place.price_level = price_level
                        if result.get("business_status"):
                            place.business_status = result["business_status"]
                        if result.get("utc_offset_minutes") is not None:
                            place.utc_offset_minutes = result["utc_offset_minutes"]
                        if result.get("opening_hours"):
                            place.hours_json = json.dumps(result["opening_hours"])
                        if result.get("website"):
                            place.website = result["website"]
                        if result.get("phone"):
                            place.phone = result["phone"]
                        if result.get("rating") is not None:
                            place.rating = result["rating"]
                        
                        # Строгий режим ENRICHED
                        has_coords = (place.lat is not None and place.lng is not None)
                        has_photo = bool(place.picture_url and str(place.picture_url).strip())
                        if has_coords and has_photo:
                            place.processing_status = 'enriched'
                        else:
                            # откатываем статус на summarized для повторной попытки позже
                            place.processing_status = 'summarized'
                        db.commit()
                        print(f"DEBUG: Сохранено в базу - адрес: {place.address}, цена: {place.price_level}, сайт: {place.website}")
                finally:
                    db.close()
                
            else:
                # Логируем ошибку
                ShadowEventLogger.log_event(
                    place_id=payload.place_id_internal,
                    agent="enricher",
                    code="NOT_FOUND",
                    level="warn",
                    note="Место не найдено в Google"
                )
                
                payload.add_diagnostic("enricher", "warn", "NOT_FOUND", "Место не найдено в Google")
            
            return payload
            
        except Exception as e:
            # Логируем ошибку
            ShadowEventLogger.log_event(
                place_id=payload.place_id_internal,
                agent="enricher",
                code="PROCESSING_ERROR",
                level="error",
                note=f"Ошибка обогащения: {str(e)}"
            )
            
            payload.add_diagnostic("enricher", "error", "PROCESSING_ERROR", str(e))
            return payload
