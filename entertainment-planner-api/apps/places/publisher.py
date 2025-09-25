#!/usr/bin/env python3
"""
Publisher функция для финальной публикации мест
Итерация 6: Publisher как функция
"""

import logging
from typing import Dict, Any, List
from datetime import datetime
from apps.places.dto import PlaceDTO
from apps.places.shadow_utils import ShadowEventLogger, ShadowQualityManager

logger = logging.getLogger(__name__)


def publish_place(payload: PlaceDTO) -> Dict[str, Any]:
    """Финальная публикация места"""
    try:
        # Логируем начало публикации
        ShadowEventLogger.log_event(
            place_id=payload.place_id_internal,
            agent="publisher",
            code="PUBLISH_START",
            level="info",
            note="Начало финальной публикации"
        )
        
        # Финальная валидация
        validation_result = _validate_for_publication(payload)
        
        if not validation_result["is_valid"]:
            # Не прошло валидацию
            ShadowEventLogger.log_event(
                place_id=payload.place_id_internal,
                agent="publisher",
                code="PUBLISH_FAILED",
                level="error",
                note=f"Не прошло валидацию: {', '.join(validation_result['issues'])}"
            )
            
            return {
                "success": False,
                "error": f"Валидация не пройдена: {', '.join(validation_result['issues'])}",
                "issues": validation_result["issues"]
            }
        
        # Устанавливаем финальные флаги качества
        _set_final_quality_flags(payload)
        
        # Логируем успешную публикацию
        ShadowEventLogger.log_event(
            place_id=payload.place_id_internal,
            agent="publisher",
            code="PUBLISH_SUCCESS",
            level="info",
            note="Место успешно опубликовано"
        )
        
        # Добавляем в историю
        payload.add_history("publisher", "Место опубликовано")
        
        return {
            "success": True,
            "published_at": datetime.now().isoformat(),
            "quality_flags": payload.quality_flags
        }
        
    except Exception as e:
        logger.error(f"Ошибка публикации места {payload.place_id_internal}: {e}")
        
        ShadowEventLogger.log_event(
            place_id=payload.place_id_internal,
            agent="publisher",
            code="PUBLISH_ERROR",
            level="error",
            note=f"Ошибка публикации: {str(e)}"
        )
        
        return {
            "success": False,
            "error": str(e)
        }


def _validate_for_publication(payload: PlaceDTO) -> Dict[str, Any]:
    """Финальная валидация для публикации"""
    issues = []
    
    # Критичные проверки
    if not payload.clean.get("name"):
        issues.append("MISSING_NAME")
    
    if not payload.clean.get("summary"):
        issues.append("MISSING_SUMMARY")
    
    coords = payload.google.get("coords", {})
    if not coords.get("lat") or not coords.get("lng"):
        issues.append("MISSING_COORDS")
    
    # Некритичные проверки (предупреждения)
    warnings = []
    
    if not payload.clean.get("tags_csv"):
        warnings.append("WEAK_TAGS")
    
    if not payload.google.get("photos"):
        warnings.append("NO_PHOTOS")
    
    if not payload.google.get("place_id"):
        warnings.append("NO_GOOGLE_ID")
    
    # Логируем предупреждения
    for warning in warnings:
        ShadowEventLogger.log_event(
            place_id=payload.place_id_internal,
            agent="publisher",
            code=warning,
            level="warn",
            note=f"Предупреждение: {warning}"
        )
    
    return {
        "is_valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings
    }


def _set_final_quality_flags(payload: PlaceDTO):
    """Установить финальные флаги качества"""
    # Оцениваем качество саммари
    summary = payload.clean.get("summary", "")
    if len(summary) > 100:
        payload.update_quality_flag("summary", "excellent")
    elif len(summary) > 50:
        payload.update_quality_flag("summary", "good")
    else:
        payload.update_quality_flag("summary", "weak")
    
    # Оцениваем качество тегов
    tags = payload.clean.get("tags_csv", "")
    tag_count = len(tags.split(",")) if tags else 0
    if tag_count >= 5:
        payload.update_quality_flag("tags", "rich")
    elif tag_count >= 3:
        payload.update_quality_flag("tags", "good")
    else:
        payload.update_quality_flag("tags", "sparse")
    
    # Оцениваем качество фото
    photos = payload.google.get("photos", [])
    if len(photos) >= 2:
        payload.update_quality_flag("photos", "excellent")
    elif len(photos) >= 1:
        payload.update_quality_flag("photos", "ok")
    else:
        payload.update_quality_flag("photos", "missing")
    
    # Оцениваем координаты
    coords = payload.google.get("coords", {})
    if coords.get("lat") and coords.get("lng"):
        payload.update_quality_flag("coords", "present")
    else:
        payload.update_quality_flag("coords", "missing")


def batch_publish(place_ids: List[int]) -> Dict[str, Any]:
    """Массовая публикация мест"""
    results = []
    success_count = 0
    error_count = 0
    
    for place_id in place_ids:
        try:
            # Здесь нужно получить PlaceDTO из базы
            # Для демонстрации создаем заглушку
            payload = PlaceDTO(
                place_id_internal=place_id,
                clean={"name": f"Place {place_id}", "summary": "Test summary"},
                google={"coords": {"lat": 13.7563, "lng": 100.5018}}
            )
            
            result = publish_place(payload)
            results.append({
                "place_id": place_id,
                "success": result["success"],
                "error": result.get("error")
            })
            
            if result["success"]:
                success_count += 1
            else:
                error_count += 1
                
        except Exception as e:
            results.append({
                "place_id": place_id,
                "success": False,
                "error": str(e)
            })
            error_count += 1
    
    return {
        "total": len(place_ids),
        "success": success_count,
        "errors": error_count,
        "results": results
    }
