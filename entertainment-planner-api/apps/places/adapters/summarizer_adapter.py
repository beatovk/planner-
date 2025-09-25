#!/usr/bin/env python3
"""
Адаптер для Summarizer агента
Итерация 3: Адаптеры поверх существующих воркеров
"""

from typing import Dict, Any
from apps.places.dto import PlaceDTO
from apps.places.shadow_utils import ShadowEventLogger
from apps.places.workers.gpt_normalizer import GPTNormalizerWorker


class SummarizerAdapter:
    """Адаптер для GPT Normalizer (Summarizer)"""
    
    def __init__(self):
        self.gpt_normalizer = GPTNormalizerWorker()
    
    def process(self, payload: PlaceDTO) -> PlaceDTO:
        """Обработать место через Summarizer"""
        try:
            # Логируем начало обработки
            ShadowEventLogger.log_event(
                place_id=payload.place_id_internal,
                agent="summarizer",
                code="PROCESSING_START",
                level="info",
                note="Начало обработки через Summarizer"
            )
            
            # Увеличиваем счетчик попыток
            payload.increment_attempt("summarizer")
            
            # Подготавливаем данные для GPT Normalizer
            gpt_payload = {
                "id": payload.place_id_internal,
                "name": payload.clean.get("name", ""),
                "description_full": payload.clean.get("full_description", ""),
                "category": payload.clean.get("category", ""),
                "tags_csv": payload.clean.get("tags_csv", ""),
                "summary": payload.clean.get("summary", ""),
                "hours_json": payload.clean.get("hours_json", ""),
                "price_level": payload.clean.get("price_level", 0)
            }
            
            # Вызываем GPT Normalizer
            result = self.gpt_normalizer._send_to_gpt(gpt_payload)
            
            if result and result.get("summary"):
                # Обновляем clean данные
                payload.clean["summary"] = result["summary"]
                # Обрабатываем теги - если это список, объединяем в строку
                tags = result.get("tags", "")
                if isinstance(tags, list):
                    payload.clean["tags_csv"] = ",".join(tags)
                else:
                    payload.clean["tags_csv"] = tags
                
                # Обновляем флаги качества
                if result["summary"]:
                    payload.update_quality_flag("summary", "good")
                if result.get("tags"):
                    payload.update_quality_flag("tags", "rich")
                
                # Логируем успех
                ShadowEventLogger.log_event(
                    place_id=payload.place_id_internal,
                    agent="summarizer",
                    code="SUCCESS",
                    level="info",
                    note=f"Создано саммари: {result['summary'][:50]}..."
                )
                
                # Добавляем в историю
                payload.add_history("summarizer", f"Создано саммари и теги")
                
            else:
                # Логируем ошибку
                ShadowEventLogger.log_event(
                    place_id=payload.place_id_internal,
                    agent="summarizer",
                    code="NO_SUMMARY",
                    level="error",
                    note="Не удалось создать саммари"
                )
                
                payload.add_diagnostic("summarizer", "error", "NO_SUMMARY", "Не удалось создать саммари")
            
            return payload
            
        except Exception as e:
            # Логируем ошибку
            ShadowEventLogger.log_event(
                place_id=payload.place_id_internal,
                agent="summarizer",
                code="PROCESSING_ERROR",
                level="error",
                note=f"Ошибка обработки: {str(e)}"
            )
            
            payload.add_diagnostic("summarizer", "error", "PROCESSING_ERROR", str(e))
            return payload
