#!/usr/bin/env python3
"""
Адаптер для Editor агента (AI Editor)
Итерация 3: Адаптеры поверх существующих воркеров
"""

from typing import Dict, Any
from apps.places.dto import PlaceDTO
from apps.places.shadow_utils import ShadowEventLogger
from apps.places.workers.ai_editor import AIEditorAgent


class EditorAdapter:
    """Адаптер для AI Editor"""
    
    def __init__(self):
        self.ai_editor = AIEditorAgent()
    
    def process(self, payload: PlaceDTO) -> PlaceDTO:
        """Обработать место через Editor"""
        try:
            # Логируем начало обработки
            ShadowEventLogger.log_event(
                place_id=payload.place_id_internal,
                agent="editor",
                code="PROCESSING_START",
                level="info",
                note="Начало проверки через AI Editor"
            )
            
            # Увеличиваем счетчик попыток
            payload.increment_attempt("editor_cycles")
            
            # Проверяем полноту данных
            validation_result = self._validate_place(payload)
            
            if validation_result["is_valid"]:
                # Данные валидны - публикуем место
                ShadowEventLogger.log_event(
                    place_id=payload.place_id_internal,
                    agent="editor",
                    code="VALIDATION_SUCCESS",
                    level="info",
                    note="Данные прошли валидацию - публикуем место"
                )
                
                # Обновляем флаги качества
                payload.update_quality_flag("summary", "good" if payload.clean.get("summary") else "weak")
                payload.update_quality_flag("tags", "rich" if payload.clean.get("tags_csv") else "sparse")
                payload.update_quality_flag("photos", "ok" if payload.google.get("photos") else "missing")
                payload.update_quality_flag("coords", "present" if payload.google.get("coords") else "missing")
                
                # Публикуем место в базе данных
                self._publish_place(payload)
                
                # Добавляем в историю
                payload.add_history("editor", "Опубликовано")
                
            else:
                # Данные невалидны, нужна ревизия
                ShadowEventLogger.log_event(
                    place_id=payload.place_id_internal,
                    agent="editor",
                    code="NEEDS_REVISION",
                    level="warn",
                    note=f"Требуется ревизия: {', '.join(validation_result['issues'])}"
                )
                
                # Добавляем диагностику
                for issue in validation_result["issues"]:
                    payload.add_diagnostic("editor", "warn", "NEEDS_REVISION", issue)
                
                # Добавляем в историю
                payload.add_history("editor", f"Требуется ревизия: {', '.join(validation_result['issues'])}")
            
            return payload
            
        except Exception as e:
            # Логируем ошибку
            ShadowEventLogger.log_event(
                place_id=payload.place_id_internal,
                agent="editor",
                code="PROCESSING_ERROR",
                level="error",
                note=f"Ошибка проверки: {str(e)}"
            )
            
            payload.add_diagnostic("editor", "error", "PROCESSING_ERROR", str(e))
            return payload
    
    def _validate_place(self, payload: PlaceDTO) -> Dict[str, Any]:
        """Валидация места - минимальные требования для публикации"""
        issues = []
        
        # Обязательные поля для публикации
        if not payload.clean.get("name"):
            issues.append("MISSING_NAME")
        
        # Google обогащение (координаты) - обязательно
        coords = payload.google.get("coords", {})
        if not coords.get("lat") or not coords.get("lng"):
            issues.append("MISSING_COORDS")
        
        # Описание или саммари - хотя бы что-то одно
        has_description = bool(payload.clean.get("description_full") and payload.clean.get("description_full").strip())
        has_summary = bool(payload.clean.get("summary") and payload.clean.get("summary").strip())
        
        if not has_description and not has_summary:
            issues.append("MISSING_DESCRIPTION_OR_SUMMARY")
        
        # Рейтинг и фото - желательно, но не блокируют публикацию
        if payload.google.get("rating") is None:
            issues.append("MISSING_RATING")
        
        if not payload.google.get("photos"):
            issues.append("MISSING_PHOTOS")
        
        # Публикуем, если есть только обязательные поля
        return {
            "is_valid": len([issue for issue in issues if issue not in ["MISSING_RATING", "MISSING_PHOTOS"]]) == 0,
            "issues": issues
        }
    
    def _publish_place(self, payload: PlaceDTO):
        """Публикует место в базе данных"""
        from apps.core.db import SessionLocal
        from apps.places.models import Place
        from datetime import datetime, timezone
        
        db = SessionLocal()
        try:
            place = db.query(Place).get(payload.place_id_internal)
            if place:
                place.processing_status = 'published'
                place.updated_at = datetime.now(timezone.utc)
                db.commit()
                
                ShadowEventLogger.log_event(
                    place_id=payload.place_id_internal,
                    agent="editor",
                    code="PUBLISHED",
                    level="info",
                    note="Место успешно опубликовано"
                )
        except Exception as e:
            db.rollback()
            ShadowEventLogger.log_event(
                place_id=payload.place_id_internal,
                agent="editor",
                code="PUBLISH_ERROR",
                level="error",
                note=f"Ошибка публикации: {str(e)}"
            )
        finally:
            db.close()
