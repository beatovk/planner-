#!/usr/bin/env python3
"""
Утилиты для теневой схемы протокола агентов
Итерация 2: Статусы в тень
"""

import json
from typing import Dict, Any, Optional
from datetime import datetime
from apps.places.models import Place, PlaceEvent, PlaceStatus
from apps.core.db import SessionLocal


class ShadowStatusMapper:
    """Маппер для теневых статусов"""
    
    # Маппинг старых статусов на новые
    LEGACY_TO_NEW = {
        "new": PlaceStatus.NEW.value,
        "published": PlaceStatus.PUBLISHED.value,
        "error": PlaceStatus.ERROR.value
    }
    
    # Маппинг новых статусов на старые (для обратной совместимости)
    NEW_TO_LEGACY = {
        PlaceStatus.NEW.value: "new",
        PlaceStatus.SUMMARIZED.value: "new",  # временно мапим на new
        PlaceStatus.ENRICHED.value: "new",    # временно мапим на new
        PlaceStatus.NEEDS_REVISION.value: "new",  # временно мапим на new
        PlaceStatus.REVIEW_PENDING.value: "new",  # временно мапим на new
        PlaceStatus.PUBLISHED.value: "published",
        PlaceStatus.FAILED.value: "error",
        PlaceStatus.ERROR.value: "error"
    }
    
    @classmethod
    def get_legacy_status(cls, new_status: str) -> str:
        """Получить старый статус для обратной совместимости"""
        return cls.NEW_TO_LEGACY.get(new_status, "new")
    
    @classmethod
    def get_new_status(cls, legacy_status: str) -> str:
        """Получить новый статус из старого"""
        return cls.LEGACY_TO_NEW.get(legacy_status, PlaceStatus.NEW.value)


class ShadowEventLogger:
    """Логгер событий для теневой схемы"""
    
    @staticmethod
    def log_event(place_id: int, agent: str, code: str, level: str, note: str = None):
        """Записать событие в теневую схему"""
        db = SessionLocal()
        try:
            event = PlaceEvent(
                place_id=place_id,
                agent=agent,
                code=code,
                level=level,
                note=note
            )
            db.add(event)
            db.commit()
        except Exception as e:
            print(f"Ошибка записи события: {e}")
            db.rollback()
        finally:
            db.close()
    
    @staticmethod
    def get_place_events(place_id: int) -> list:
        """Получить события места"""
        db = SessionLocal()
        try:
            events = db.query(PlaceEvent).filter(
                PlaceEvent.place_id == place_id
            ).order_by(PlaceEvent.ts.desc()).all()
            return events
        finally:
            db.close()


class ShadowAttemptsManager:
    """Менеджер попыток для теневой схемы"""
    
    @staticmethod
    def get_attempts(place: Place) -> Dict[str, int]:
        """Получить попытки агентов"""
        if not place.attempts:
            return {"summarizer": 0, "enricher": 0, "editor_cycles": 0}
        try:
            return json.loads(place.attempts)
        except (json.JSONDecodeError, TypeError):
            return {"summarizer": 0, "enricher": 0, "editor_cycles": 0}
    
    @staticmethod
    def increment_attempt(place: Place, agent: str) -> Place:
        """Увеличить счетчик попыток агента"""
        attempts = ShadowAttemptsManager.get_attempts(place)
        attempts[agent] = attempts.get(agent, 0) + 1
        place.attempts = json.dumps(attempts)
        return place
    
    @staticmethod
    def set_attempts(place: Place, attempts: Dict[str, int]) -> Place:
        """Установить попытки агентов"""
        place.attempts = json.dumps(attempts)
        return place


class ShadowQualityManager:
    """Менеджер флагов качества для теневой схемы"""
    
    @staticmethod
    def get_quality_flags(place: Place) -> Dict[str, str]:
        """Получить флаги качества"""
        if not place.quality_flags:
            return {"summary": "unknown", "tags": "unknown", "photos": "unknown", "coords": "unknown"}
        try:
            return json.loads(place.quality_flags)
        except (json.JSONDecodeError, TypeError):
            return {"summary": "unknown", "tags": "unknown", "photos": "unknown", "coords": "unknown"}
    
    @staticmethod
    def set_quality_flags(place: Place, flags: Dict[str, str]) -> Place:
        """Установить флаги качества"""
        place.quality_flags = json.dumps(flags)
        return place
    
    @staticmethod
    def update_quality_flag(place: Place, flag: str, value: str) -> Place:
        """Обновить один флаг качества"""
        flags = ShadowQualityManager.get_quality_flags(place)
        flags[flag] = value
        place.quality_flags = json.dumps(flags)
        return place


def update_shadow_status(place: Place, new_status: str, reason: str = None):
    """Обновить теневой статус места"""
    # Обновляем основной статус (для совместимости)
    place.processing_status = new_status
    
    # Логируем событие
    ShadowEventLogger.log_event(
        place_id=place.id,
        agent="system",
        code="STATUS_CHANGE",
        level="info",
        note=f"Статус изменен на {new_status}. Причина: {reason or 'не указана'}"
    )
    
    # Обновляем время
    place.updated_at = datetime.now()
