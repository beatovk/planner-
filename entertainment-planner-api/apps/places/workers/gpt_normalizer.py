#!/usr/bin/env python3
"""GPT Normalizer Worker - фоновый модуль для нормализации данных мест"""

import asyncio
import json
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session
from apps.core.db import SessionLocal
from apps.places.models import Place
from .gpt_client import GPTClient

logger = logging.getLogger(__name__)
LOCK_PATH = "/tmp/ep_writer.lock"


class GPTNormalizerWorker:
    """Worker для нормализации данных мест через GPT API"""
    
    def __init__(self, batch_size: int = 5, api_key: str = None):
        self.batch_size = batch_size
        self.api_key = api_key or self._get_api_key()
        self.gpt_client = GPTClient(self.api_key)
        self.processed_count = 0
        self.error_count = 0
        self.success_count = 0
    
    def _get_api_key(self) -> str:
        """Получение API ключа из переменных окружения"""
        import os
        from dotenv import load_dotenv
        
        # Загружаем .env файл
        load_dotenv()
        
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY не найден в переменных окружения")
        return api_key
    
    def run(self):
        """Основной метод запуска worker'а"""
        logger.info("Запуск GPT Normalizer Worker")
        # глобальный маркер для API: открыть БД в read-only
        os.environ['EP_API_READONLY']='1'
        
        try:
            self._process_batches()
            self._log_results()
        except Exception as e:
            logger.error(f"Ошибка в worker: {e}")
            raise
    
    def _process_batches(self):
        """Обработка записей батчами"""
        db = SessionLocal()
        try:
            while True:
                # Получаем батч: 'new' без ограничений и 'error' только со старым updated_at (бэк-офф 30 минут)
                cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
                places = (
                    db.query(Place)
                    .filter(
                        (
                            (Place.processing_status == 'new')
                        ) | (
                            (Place.processing_status == 'error') &
                            ((Place.updated_at.is_(None)) | (Place.updated_at < cutoff))
                        )
                    )
                    .limit(self.batch_size)
                    .all()
                )
                
                if not places:
                    logger.info("Нет записей для обработки")
                    break
                
                logger.info(f"Обрабатываем батч из {len(places)} записей")
                
                for place in places:
                    try:
                        self._process_place(place, db)
                    except Exception as e:
                        logger.error(f"Ошибка обработки места {place.id}: {e}")
                        self.error_count += 1
                        self._mark_as_error(place, str(e), db)
                
                db.commit()  # batch-commit (не используется, коммитим пок-стучно)  # batch-commit
                self.processed_count += len(places)
                
        finally:
            db.close()
    
    def _process_place(self, place: Place, db: Session):
        """Обработка одного места через GPT"""
        logger.info(f"Обрабатываем место: {place.name}")
        # Строго: не генерим summary, если нет description_full
        if not place.description_full or not str(place.description_full).strip():
            logger.info("Пропуск: пустой description_full — сначала fill_descriptions")
            return
        
        # Формируем payload для GPT
        payload = self._create_payload(place)
        
        # Отправляем в GPT
        response = self._send_to_gpt(payload)
        
        # Обновляем запись
        self._update_place(place, response, db)
        
        self.success_count += 1
    
    def _create_payload(self, place: Place) -> Dict[str, Any]:
        """Создание payload для отправки в GPT"""
        return {
            "id": place.id,
            "name": place.name,
            "description_full": place.description_full,
            "summary": place.summary,
            "tags_csv": place.tags_csv,
            "address": place.address,
            "hours_json": place.hours_json,
            "hours_text": self._extract_hours_text(place),
            "gmaps_url": place.gmaps_url,
            "lat": place.lat,
            "lng": place.lng
        }
    
    def _extract_hours_text(self, place: Place) -> Optional[str]:
        """Извлечение текста часов работы из различных полей"""
        if place.hours_json:
            return place.hours_json
        
        # Ищем в описании
        if place.description_full:
            import re
            # Простой паттерн для поиска часов
            hours_pattern = r'Open[^.]*|Closed[^.]*|Mon[^.]*|Tue[^.]*|Wed[^.]*|Thu[^.]*|Fri[^.]*|Sat[^.]*|Sun[^.]*'
            match = re.search(hours_pattern, place.description_full)
            if match:
                return match.group(0)
        
        return None
    
    def _send_to_gpt(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Отправка данных в GPT API"""
        return self.gpt_client.normalize_place_data(payload)
    
    def _update_place(self, place: Place, response: Dict[str, Any], db: Session):
        """Обновление записи на основе ответа GPT"""
        # Обновляем только поля, которые должен заполнять GPT worker
        place.summary = response.get('summary')
        # merge tags (lower, dedupe)
        new_tags = [t.strip().lower() for t in (response.get('tags') or []) if t and t.strip()]
        old_tags = [t.strip().lower() for t in (place.tags_csv or '').split(',') if t.strip()]
        merged = []
        seen = set()
        for t in old_tags + new_tags:
            if t and t not in seen:
                seen.add(t); merged.append(t)
        place.tags_csv = ','.join(merged) if merged else None

        # category из первых category:* тегов
        cat = next((t.split(':',1)[1] for t in merged if t.startswith('category:') and ':' in t), None)
        if cat:
            place.category = cat

        # Сохраняем signals как JSON из новой структуры signals
        signals_data = response.get('signals') or {}
        if isinstance(signals_data, dict):
            place.signals = signals_data
        else:
            # fallback для старого формата interest_signals
            interest_signals = response.get('interest_signals') or {}
            if isinstance(interest_signals, dict):
                place.signals = interest_signals
            elif isinstance(interest_signals, list):
                place.signals = {k: True for k in interest_signals}
            else:
                place.signals = {}
        
        # Инференция кухонь из блюд (временно отключена)
        # TODO: Восстановить после исправления проблем с воркером
        try:
            # Временно отключаем инференцию кухонь
            logger.debug("Cuisine inference temporarily disabled")
            pass
            
            # from apps.places.services.cuisine_inference import CuisineInferenceService
            # cuisine_service = CuisineInferenceService()
            # 
            # # Составляем текстовый блоб для fallback поиска
            # text_parts = []
            # if place.name:
            #     text_parts.append(place.name)
            # if place.summary:
            #     text_parts.append(place.summary)
            # if place.description_full:
            #     text_parts.append(place.description_full)
            # text_blob = " ".join(text_parts)
            # 
            # # Инферим кухни
            # cuisines_to_add, cuisine_evidence = cuisine_service.infer_cuisines_from_dishes(
            #     place.tags_csv or "", text_blob
            # )
            # 
            # if cuisines_to_add:
            #     # Добавляем cuisine:* теги
            #     cuisine_tags = [f"cuisine:{c}" for c in cuisines_to_add]
            #     merged_with_cuisines = merged + cuisine_tags
            #     
            #     # Убираем дубликаты
            #     seen = set()
            #     final_tags = []
            #     for tag in merged_with_cuisines:
            #         if tag not in seen:
            #             seen.add(tag)
            #             final_tags.append(tag)
            #     
            #     place.tags_csv = ','.join(final_tags) if final_tags else None
            #     
            #     # Обновляем signals с информацией об инференции
            #     current_signals = place.signals or {}
            #     current_signals["cuisine_inferred"] = cuisine_evidence
            #     place.signals = current_signals
            #     
            #     logger.debug(f"Added cuisines to place {place.id}: {cuisines_to_add}")
                
        except Exception as e:
            logger.warning(f"Failed to infer cuisines for place {place.id}: {e}")
        
        # Пересчитать bitset/метаданные - отключено до исправления VibesOntology
        # TODO: Восстановить после исправления VibesOntology.from_yaml() метода
        try:
            # Временно отключаем bitset computation
            place.tag_bitset = None
            logger.debug("Bitset computation skipped")
        except Exception as _:
            logger.warning("Bitset recompute skipped")

        # Определяем статус на основе confidence
        confidence = response.get('confidence', 0)
        validation_notes = response.get('validation_notes')
        
        if confidence < 0.7 or validation_notes:
            place.processing_status = 'error'
            place.last_error = validation_notes
        else:
            place.processing_status = 'summarized'
        
        place.updated_at = datetime.now(timezone.utc)
        db.flush()
        db.commit()  # batch-commit (не используется, коммитим пок-стучно)
    
    def _mark_as_error(self, place: Place, error_msg: str, db: Session):
        """Помечаем запись как ошибочную"""
        place.processing_status = 'error'
        place.last_error = error_msg
        place.updated_at = datetime.now(timezone.utc)
        db.flush()
        db.commit()  # batch-commit (не используется, коммитим пок-стучно)
    
    def _log_results(self):
        """Логирование результатов работы"""
        logger.info(f"Обработка завершена:")
        logger.info(f"- Всего обработано: {self.processed_count}")
        logger.info(f"- Успешно: {self.success_count}")
        logger.info(f"- Ошибок: {self.error_count}")


if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Запуск worker'а
    worker = GPTNormalizerWorker()
    worker.run()


import os, sqlite3
def backup_sqlite(sqlalchemy_engine, out_path:str):
    # без блокировок приложения: используем online backup API
    db_path = sqlalchemy_engine.url.database
    if not db_path:
        return
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    src = sqlite3.connect(db_path, timeout=30)
    dst = sqlite3.connect(out_path)
    with dst:
        src.backup(dst)
    src.close(); dst.close()

BATCH_BACKUP_N = 25
