#!/usr/bin/env python3
"""
Исправленный GPT воркер с новой сессией для каждого места
"""

import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from apps.core.db import SessionLocal
from apps.places.models import Place
from apps.places.workers.gpt_client import GPTClient

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FixedGPTWorker:
    """Исправленный воркер с новой сессией для каждого места"""
    
    def __init__(self, batch_size=1):
        self.batch_size = batch_size
        self.api_key = self._get_api_key()
        self.gpt_client = GPTClient(self.api_key)
        self.processed_count = 0
        self.error_count = 0
        self.success_count = 0
        
    def _get_api_key(self) -> str:
        """Получение API ключа из переменных окружения"""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY не найден в переменных окружения")
        return api_key
    
    def run(self):
        """Основной метод запуска worker'а"""
        logger.info("🚀 Запуск Fixed GPT Worker...")
        logger.info(f"📊 Размер батча: {self.batch_size}")
        
        try:
            while True:
                # Получаем места для обработки
                places = self._get_places_to_process()
                
                if not places:
                    logger.info("✅ Нет записей для обработки")
                    break
                
                logger.info(f"🔄 Обрабатываем батч из {len(places)} записей")
                
                for place in places:
                    try:
                        self._process_single_place(place)
                        self.success_count += 1
                    except Exception as e:
                        logger.error(f"❌ Ошибка обработки места {place.id}: {e}")
                        self.error_count += 1
                        self._mark_as_error(place, str(e))
                
                self.processed_count += len(places)
                
                # Небольшая пауза между батчами
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            raise
    
    def _get_places_to_process(self):
        """Получение мест для обработки"""
        db = SessionLocal()
        try:
            # Получаем батч: 'new' без ограничений и 'error' только со старым updated_at
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
            return places
        finally:
            db.close()
    
    def _process_single_place(self, place: Place):
        """Обработка одного места с новой сессией"""
        logger.info(f"🔄 Обрабатываем место: {place.name}")
        
        # Проверяем наличие описания
        if not place.description_full or not str(place.description_full).strip():
            logger.info("⏭️ Пропуск: пустой description_full")
            return
        
        # Создаем новую сессию для каждого места
        db = SessionLocal()
        try:
            # Получаем свежую версию места
            fresh_place = db.query(Place).filter(Place.id == place.id).first()
            if not fresh_place:
                logger.warning(f"⚠️ Место {place.id} не найдено")
                return
            
            # Обрабатываем через GPT
            payload = {
                'id': fresh_place.id,
                'name': fresh_place.name,
                'description_full': fresh_place.description_full,
                'category': fresh_place.category,
                'source': fresh_place.source
            }
            result = self.gpt_client.normalize_place_data(payload)
            
            if result:
                # Обновляем место
                fresh_place.category = result.get('category', fresh_place.category)
                fresh_place.summary = result.get('summary', fresh_place.summary)
                fresh_place.tags_csv = result.get('tags_csv', fresh_place.tags_csv)
                fresh_place.processing_status = 'summarized'
                fresh_place.updated_at = datetime.now(timezone.utc)
                fresh_place.signals = result.get('signals', {})
                
                db.commit()
                logger.info(f"✅ Место {fresh_place.name} обработано успешно")
            else:
                logger.warning(f"⚠️ GPT не вернул результат для {fresh_place.name}")
                
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Ошибка обработки места {place.id}: {e}")
            raise
        finally:
            db.close()
    
    def _mark_as_error(self, place: Place, error_msg: str):
        """Помечаем место как ошибочное"""
        db = SessionLocal()
        try:
            fresh_place = db.query(Place).filter(Place.id == place.id).first()
            if fresh_place:
                fresh_place.processing_status = 'error'
                fresh_place.last_error = error_msg
                fresh_place.updated_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as e:
            logger.error(f"❌ Ошибка при пометке места как ошибочного: {e}")
        finally:
            db.close()

def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fixed GPT Worker')
    parser.add_argument('--batch-size', type=int, default=1, help='Размер батча')
    args = parser.parse_args()
    
    # Проверяем API ключ
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ Ошибка: OPENAI_API_KEY не найден в переменных окружения")
        sys.exit(1)
    
    print("🔑 API ключ: установлен")
    print("-" * 50)
    
    worker = FixedGPTWorker(batch_size=args.batch_size)
    worker.run()

if __name__ == "__main__":
    main()
