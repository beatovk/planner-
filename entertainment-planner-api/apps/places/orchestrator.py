#!/usr/bin/env python3
"""
Оркестратор для протокола агентов
Итерация 4: Оркестратор с feature-флагом и канарейкой
"""

import os
import random
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from apps.core.db import SessionLocal
from apps.places.models import Place, PlaceStatus
from apps.places.dto import PlaceDTO
from apps.places.shadow_utils import ShadowEventLogger, ShadowAttemptsManager, ShadowQualityManager
from apps.places.adapters.summarizer_adapter import SummarizerAdapter
from apps.places.adapters.enricher_adapter import EnricherAdapter
from apps.places.adapters.editor_adapter import EditorAdapter
from apps.places.publisher import publish_place

logger = logging.getLogger(__name__)

# Feature-флаг для нового протокола
ORCH_V2_ENABLED = os.getenv('ORCH_V2_ENABLED', 'false').lower() == 'true'
CANARY_PERCENTAGE = float(os.getenv('CANARY_PERCENTAGE', '10.0'))


class LoopGuard:
    """Функциональный LoopGuard для контроля циклов"""
    
    @staticmethod
    def can_retry_editor(payload: PlaceDTO) -> bool:
        """Проверить, можно ли повторить попытку Editor"""
        editor_cycles = payload.attempts.get("editor_cycles", 0)
        return editor_cycles < 3
    
    @staticmethod
    def should_fail(payload: PlaceDTO) -> bool:
        """Проверить, нужно ли перевести в failed"""
        editor_cycles = payload.attempts.get("editor_cycles", 0)
        return editor_cycles >= 3


class PlaceProcessor:
    """Оркестратор для обработки мест по новому протоколу"""
    
    def __init__(self):
        self.summarizer = SummarizerAdapter()
        self.enricher = EnricherAdapter()
        self.editor = EditorAdapter()
    
    def process_place(self, place_id: int) -> Dict[str, Any]:
        """Обработать место по новому протоколу"""
        db = SessionLocal()
        try:
            # Получаем место
            place = db.query(Place).filter(Place.id == place_id).first()
            if not place:
                return {"success": False, "error": "Место не найдено"}
            
            # Создаем DTO
            payload = PlaceDTO.from_db(place)
            
            # Логируем начало обработки
            ShadowEventLogger.log_event(
                place_id=place_id,
                agent="orchestrator",
                code="PROCESSING_START",
                level="info",
                note="Начало обработки по новому протоколу"
            )
            
            # Обрабатываем по статусу
            if payload.status == PlaceStatus.NEW.value:
                payload = self._process_new(payload)
            elif payload.status == PlaceStatus.SUMMARIZED.value:
                payload = self._process_summarized(payload)
            elif payload.status == PlaceStatus.ENRICHED.value:
                payload = self._process_enriched(payload)
            elif payload.status == PlaceStatus.REVIEW_PENDING.value:
                payload = self._process_review_pending(payload)
            else:
                return {"success": False, "error": f"Неизвестный статус: {payload.status}"}
            
            # Применяем изменения к базе
            self._apply_changes(place, payload, db)
            
            return {
                "success": True,
                "status": payload.status,
                "attempts": payload.attempts,
                "quality_flags": payload.quality_flags
            }
            
        except Exception as e:
            logger.error(f"Ошибка обработки места {place_id}: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close()
    
    def _process_new(self, payload: PlaceDTO) -> PlaceDTO:
        """Обработать место со статусом NEW"""
        # Summarizer
        payload = self.summarizer.process(payload)
        payload.status = PlaceStatus.SUMMARIZED.value
        
        return payload
    
    def _process_summarized(self, payload: PlaceDTO) -> PlaceDTO:
        """Обработать место со статусом SUMMARIZED"""
        # Enricher
        payload = self.enricher.process(payload)
        payload.status = PlaceStatus.ENRICHED.value
        
        return payload
    
    def _process_enriched(self, payload: PlaceDTO) -> PlaceDTO:
        """Обработать место со статусом ENRICHED"""
        # Editor
        payload = self.editor.process(payload)
        
        # Проверяем результат валидации
        if payload.diagnostics:
            # Есть проблемы, нужна ревизия
            payload.status = PlaceStatus.NEEDS_REVISION.value
        else:
            # Все ок, отправляем в Publisher
            publish_result = publish_place(payload)
            if publish_result["success"]:
                payload.status = PlaceStatus.PUBLISHED.value
            else:
                payload.status = PlaceStatus.FAILED.value
                payload.add_diagnostic("publisher", "error", "PUBLISH_FAILED", publish_result.get("error"))
        
        return payload
    
    def _process_review_pending(self, payload: PlaceDTO) -> PlaceDTO:
        """Обработать место со статусом REVIEW_PENDING"""
        # Editor повторная проверка
        payload = self.editor.process(payload)
        
        # Проверяем LoopGuard
        if not LoopGuard.can_retry_editor(payload):
            payload.status = PlaceStatus.FAILED.value
            ShadowEventLogger.log_event(
                place_id=payload.place_id_internal,
                agent="orchestrator",
                code="LOOP_GUARD_TRIGGERED",
                level="error",
                note="Превышено максимальное количество циклов Editor"
            )
        elif payload.diagnostics:
            # Все еще есть проблемы
            payload.status = PlaceStatus.NEEDS_REVISION.value
        else:
            # Все ок, отправляем в Publisher
            publish_result = publish_place(payload)
            if publish_result["success"]:
                payload.status = PlaceStatus.PUBLISHED.value
            else:
                payload.status = PlaceStatus.FAILED.value
                payload.add_diagnostic("publisher", "error", "PUBLISH_FAILED", publish_result.get("error"))
        
        return payload
    
    def _apply_changes(self, place: Place, payload: PlaceDTO, db):
        """Применить изменения к модели Place"""
        # Обновляем основные поля
        patch = payload.to_db_patch()
        for key, value in patch.items():
            setattr(place, key, value)
        
        # Обновляем время
        place.updated_at = datetime.now()
        
        # Если статус published, устанавливаем published_at
        if payload.status == PlaceStatus.PUBLISHED.value:
            place.published_at = datetime.now()
        
        db.commit()


class LegacyPlaceProcessor:
    """Обработчик для старого протокола (обратная совместимость)"""
    
    def process_place(self, place_id: int) -> Dict[str, Any]:
        """Обработать место по старому протоколу"""
        # Здесь можно добавить логику старого протокола
        # Пока просто возвращаем успех
        return {"success": True, "status": "legacy"}


def should_use_new_protocol(place_id: int) -> bool:
    """Определить, использовать ли новый протокол (канарейка)"""
    if not ORCH_V2_ENABLED:
        return False
    
    # Используем детерминированную канарейку на основе place_id
    random.seed(place_id)
    return random.random() < (CANARY_PERCENTAGE / 100.0)


def process_place(place_id: int) -> Dict[str, Any]:
    """Главная функция обработки места"""
    try:
        if should_use_new_protocol(place_id):
            # Новый протокол
            processor = PlaceProcessor()
            result = processor.process_place(place_id)
            result["protocol"] = "v2"
        else:
            # Старый протокол
            processor = LegacyPlaceProcessor()
            result = processor.process_place(place_id)
            result["protocol"] = "v1"
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка обработки места {place_id}: {e}")
        return {"success": False, "error": str(e), "protocol": "unknown"}


def process_batch(place_ids: list) -> Dict[str, Any]:
    """Обработать батч мест"""
    results = []
    v1_count = 0
    v2_count = 0
    
    for place_id in place_ids:
        result = process_place(place_id)
        results.append(result)
        
        if result.get("protocol") == "v1":
            v1_count += 1
        elif result.get("protocol") == "v2":
            v2_count += 1
    
    return {
        "total": len(place_ids),
        "v1_protocol": v1_count,
        "v2_protocol": v2_count,
        "results": results
    }


def auto_process_all_places() -> Dict[str, Any]:
    """Автоматически обработать ВСЕ места через полный цикл агентов"""
    db = SessionLocal()
    try:
        # Получаем все места, которые нужно обработать
        places_to_process = db.query(Place).filter(
            Place.processing_status.in_(['new', 'summarized', 'enriched', 'needs_revision'])
        ).all()
        
        if not places_to_process:
            return {
                "success": True,
                "message": "Нет мест для обработки",
                "total": 0,
                "processed": 0
            }
        
        print(f"🚀 Автоматическая обработка {len(places_to_process)} мест...")
        print("=" * 60)
        
        # Статистика
        stats = {
            "total": len(places_to_process),
            "processed": 0,
            "new_to_summarized": 0,
            "summarized_to_enriched": 0,
            "enriched_to_published": 0,
            "needs_revision_to_published": 0,
            "failed": 0,
            "errors": 0
        }
        
        # Обрабатываем каждое место
        for i, place in enumerate(places_to_process, 1):
            print(f"{i}/{len(places_to_process)}. {place.name} ({place.processing_status})")
            
            try:
                # Определяем следующий этап
                if place.processing_status == 'new':
                    # NEW → SUMMARIZED
                    result = _auto_process_new(place, db)
                    if result["success"]:
                        stats["new_to_summarized"] += 1
                        print(f"   ✅ Обработано саммаризатором")
                    else:
                        stats["errors"] += 1
                        print(f"   ❌ Ошибка саммаризатора: {result.get('error')}")
                
                elif place.processing_status == 'summarized':
                    # SUMMARIZED → ENRICHED
                    result = _auto_process_summarized(place, db)
                    if result["success"]:
                        stats["summarized_to_enriched"] += 1
                        print(f"   ✅ Обогащено Google API")
                    else:
                        stats["errors"] += 1
                        print(f"   ❌ Ошибка обогащения: {result.get('error')}")
                
                elif place.processing_status == 'enriched':
                    # ENRICHED → PUBLISHED
                    result = _auto_process_enriched(place, db)
                    if result["success"]:
                        stats["enriched_to_published"] += 1
                        print(f"   ✅ Опубликовано")
                    else:
                        stats["failed"] += 1
                        print(f"   ❌ Ошибка публикации: {result.get('error')}")
                
                elif place.processing_status == 'needs_revision':
                    # NEEDS_REVISION → PUBLISHED
                    result = _auto_process_revision(place, db)
                    if result["success"]:
                        stats["needs_revision_to_published"] += 1
                        print(f"   ✅ Исправлено и опубликовано")
                    else:
                        stats["failed"] += 1
                        print(f"   ❌ Ошибка исправления: {result.get('error')}")
                
                stats["processed"] += 1
                
            except Exception as e:
                stats["errors"] += 1
                print(f"   ❌ Критическая ошибка: {e}")
        
        print(f"\n✅ Автоматическая обработка завершена!")
        print(f"📊 Результат:")
        print(f"  Всего мест: {stats['total']}")
        print(f"  Обработано: {stats['processed']}")
        print(f"  NEW → SUMMARIZED: {stats['new_to_summarized']}")
        print(f"  SUMMARIZED → ENRICHED: {stats['summarized_to_enriched']}")
        print(f"  ENRICHED → PUBLISHED: {stats['enriched_to_published']}")
        print(f"  NEEDS_REVISION → PUBLISHED: {stats['needs_revision_to_published']}")
        print(f"  Ошибок: {stats['errors']}")
        print(f"  Неудачных: {stats['failed']}")
        
        return {
            "success": True,
            "message": "Автоматическая обработка завершена",
            **stats
        }
        
    except Exception as e:
        logger.error(f"Ошибка автоматической обработки: {e}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def _auto_process_new(place: Place, db) -> Dict[str, Any]:
    """Автоматически обработать NEW → SUMMARIZED"""
    try:
        from apps.places.adapters.summarizer_adapter import SummarizerAdapter
        from apps.places.dto import PlaceDTO
        
        # Создаем DTO
        payload = PlaceDTO.from_db(place)
        
        # Обрабатываем саммаризатором
        summarizer = SummarizerAdapter()
        result = summarizer.process(payload)
        
        # Обновляем место
        place.processing_status = 'summarized'
        place.summary = result.clean.get('summary')
        place.tags_csv = result.clean.get('tags_csv')
        place.category = result.clean.get('category')
        place.updated_at = datetime.now()
        
        db.commit()
        return {"success": True}
        
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}


def _auto_process_summarized(place: Place, db) -> Dict[str, Any]:
    """Автоматически обработать SUMMARIZED → ENRICHED"""
    try:
        from apps.places.adapters.enricher_adapter import EnricherAdapter
        from apps.places.dto import PlaceDTO
        
        # Создаем DTO
        payload = PlaceDTO.from_db(place)
        
        # Обрабатываем обогатителем
        enricher = EnricherAdapter()
        result = enricher.process(payload)
        
        # Обновляем место
        place.processing_status = 'enriched'
        if result.google.get('place_id'):
            place.gmaps_place_id = result.google['place_id']
            place.lat = result.google['coords']['lat']
            place.lng = result.google['coords']['lng']
            place.gmaps_url = result.google['maps_url']
            place.address = result.google.get('address')
            place.price_level = result.google.get('price_level')
            place.business_status = result.google.get('business_status')
            place.utc_offset_minutes = result.google.get('utc_offset_minutes')
            place.hours_json = result.google.get('opening_hours')
            place.website = result.google.get('website')
            place.phone = result.google.get('phone')
            place.rating = result.google.get('rating')
            if result.google.get('photos'):
                place.picture_url = result.google['photos'][0]
        
        place.updated_at = datetime.now()
        db.commit()
        return {"success": True}
        
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}


def _auto_process_enriched(place: Place, db) -> Dict[str, Any]:
    """Автоматически обработать ENRICHED → PUBLISHED"""
    try:
        from apps.places.adapters.editor_adapter import EditorAdapter
        from apps.places.dto import PlaceDTO
        
        # Создаем DTO
        payload = PlaceDTO.from_db(place)
        
        # Обрабатываем редактором
        editor = EditorAdapter()
        result = editor.process(payload)
        
        # Обновляем место
        place.processing_status = 'published'
        place.published_at = datetime.now()
        place.updated_at = datetime.now()
        
        db.commit()
        return {"success": True}
        
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}


def _auto_process_revision(place: Place, db) -> Dict[str, Any]:
    """Автоматически обработать NEEDS_REVISION → PUBLISHED"""
    try:
        from apps.places.adapters.editor_adapter import EditorAdapter
        from apps.places.dto import PlaceDTO
        
        # Создаем DTO
        payload = PlaceDTO.from_db(place)
        
        # Обрабатываем редактором
        editor = EditorAdapter()
        result = editor.process(payload)
        
        # Обновляем место
        place.processing_status = 'published'
        place.published_at = datetime.now()
        place.updated_at = datetime.now()
        
        db.commit()
        return {"success": True}
        
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
