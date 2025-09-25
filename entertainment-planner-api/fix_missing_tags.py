#!/usr/bin/env python3
"""
Временный скрипт для исправления 1220 записей без тегов
Использует логику GPT Normalizer для обработки записей в статусе 'published'
"""

import os
import sys
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.core.db import SessionLocal
from apps.places.models import Place
from apps.places.workers.gpt_client import GPTClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TagsFixer:
    """Временный скрипт для исправления записей без тегов"""
    
    def __init__(self, batch_size: int = 10, api_key: str = None):
        self.batch_size = batch_size
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY не найден в переменных окружения")
        
        self.gpt_client = GPTClient(self.api_key)
        self.processed_count = 0
        self.error_count = 0
        self.success_count = 0
        
    def run(self):
        """Основной метод запуска"""
        logger.info("🚀 Запуск исправления записей без тегов...")
        
        try:
            self._process_batches()
            self._log_results()
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            raise
    
    def _process_batches(self):
        """Обработка записей батчами"""
        while True:
            # Создаем новое соединение для каждого батча
            db = SessionLocal()
            try:
                # Получаем записи published без тегов
                places = (
                    db.query(Place)
                    .filter(
                        Place.processing_status == 'published',
                        (Place.tags_csv.is_(None) | (Place.tags_csv == ''))
                    )
                    .limit(self.batch_size)
                    .all()
                )
                
                if not places:
                    logger.info("✅ Нет записей для обработки")
                    break
                
                logger.info(f"📝 Обрабатываем батч из {len(places)} записей")
                
                for place in places:
                    try:
                        self._process_place(place, db)
                    except Exception as e:
                        logger.error(f"❌ Ошибка обработки места {place.id}: {e}")
                        self.error_count += 1
                        self._mark_as_error(place, str(e), db)
                
                db.commit()
                self.processed_count += len(places)
                
            except Exception as e:
                logger.error(f"❌ Ошибка батча: {e}")
                db.rollback()
            finally:
                db.close()
    
    def _process_place(self, place: Place, db):
        """Обработка одного места через GPT"""
        logger.info(f"🔍 Обрабатываем место: {place.name}")
        
        # Проверяем наличие описания
        if not place.description_full or not str(place.description_full).strip():
            logger.warning(f"⚠️ Пропуск: пустой description_full для {place.name}")
            return
        
        # Формируем payload для GPT
        payload = self._create_payload(place)
        
        # Отправляем в GPT
        response = self._send_to_gpt(payload)
        
        # Обновляем запись
        self._update_place(place, response, db)
        
        self.success_count += 1
        logger.info(f"✅ Место {place.name} обработано успешно")
    
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
    
    def _update_place(self, place: Place, response: Dict[str, Any], db):
        """Обновление записи на основе ответа GPT"""
        # Обновляем только теги и связанные поля, не меняем статус
        
        # merge tags (lower, dedupe)
        new_tags = [t.strip().lower() for t in (response.get('tags') or []) if t and t.strip()]
        old_tags = [t.strip().lower() for t in (place.tags_csv or '').split(',') if t.strip()]
        merged = []
        seen = set()
        for t in old_tags + new_tags:
            if t and t not in seen:
                seen.add(t)
                merged.append(t)
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
        
        # Пересчитать bitset/метаданные
        try:
            from apps.places.services.bitset_service import BitsetService
            from apps.places.schemas.vibes import VibesOntology
            import yaml
            
            with open(os.path.join(os.getcwd(), "config", "vibes.yml"), "r", encoding="utf-8") as f:
                vibescfg = yaml.safe_load(f)
            ontology = VibesOntology.from_yaml(vibescfg)
            bs = BitsetService(ontology)
            tags = [t.strip() for t in (place.tags_csv or '').split(',') if t.strip()]
            place.tag_bitset = bs.tags_to_bitset(tags)
        except Exception as e:
            logger.warning(f"Bitset recompute skipped: {e}")

        # НЕ меняем processing_status - оставляем 'published'
        place.updated_at = datetime.now(timezone.utc)
        db.flush()
    
    def _mark_as_error(self, place: Place, error_msg: str, db):
        """Помечаем запись как ошибочную"""
        place.processing_status = 'error'
        place.last_error = error_msg
        place.updated_at = datetime.now(timezone.utc)
        db.flush()
    
    def _log_results(self):
        """Логирование результатов работы"""
        logger.info("📊 Результаты исправления тегов:")
        logger.info(f"  Обработано: {self.processed_count}")
        logger.info(f"  Успешно: {self.success_count}")
        logger.info(f"  Ошибок: {self.error_count}")


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Исправление записей без тегов')
    parser.add_argument('--batch-size', type=int, default=10, help='Размер батча')
    parser.add_argument('--api-key', type=str, help='OpenAI API ключ')
    parser.add_argument('--verbose', '-v', action='store_true', help='Подробное логирование')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Set API key
    if args.api_key:
        os.environ['OPENAI_API_KEY'] = args.api_key
    
    try:
        fixer = TagsFixer(
            batch_size=args.batch_size,
            api_key=args.api_key
        )
        
        print("🤖 Запуск исправления записей без тегов...")
        print(f"📊 Размер батча: {args.batch_size}")
        print(f"🔑 API ключ: {'установлен' if os.getenv('OPENAI_API_KEY') else 'НЕ НАЙДЕН'}")
        print("-" * 50)
        
        fixer.run()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
