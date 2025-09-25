#!/usr/bin/env python3
"""
Улучшенный GPT воркер с обработкой ошибок и переподключением
"""

import os
import sys
import time
import logging
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from apps.places.workers.gpt_normalizer import GPTNormalizerWorker
from apps.core.db import SessionLocal

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RobustGPTWorker:
    """Улучшенный воркер с обработкой ошибок"""
    
    def __init__(self, batch_size=1):
        self.batch_size = batch_size
        self.max_retries = 3
        self.retry_delay = 5
        
    def run(self):
        """Запуск воркера с обработкой ошибок"""
        logger.info("🚀 Запуск Robust GPT Worker...")
        logger.info(f"📊 Размер батча: {self.batch_size}")
        
        retry_count = 0
        
        while retry_count < self.max_retries:
            try:
                # Создаем новую сессию для каждого батча
                db = SessionLocal()
                
                try:
                    worker = GPTNormalizerWorker(batch_size=self.batch_size)
                    worker.run()
                    
                    # Если успешно, сбрасываем счетчик ошибок
                    retry_count = 0
                    logger.info("✅ Батч обработан успешно")
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка в воркере: {e}")
                    retry_count += 1
                    
                    if retry_count < self.max_retries:
                        logger.info(f"🔄 Попытка {retry_count}/{self.max_retries} через {self.retry_delay} сек...")
                        time.sleep(self.retry_delay)
                    else:
                        logger.error("❌ Превышено максимальное количество попыток")
                        break
                        
                finally:
                    db.close()
                    
                # Небольшая пауза между батчами
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Критическая ошибка: {e}")
                retry_count += 1
                
                if retry_count < self.max_retries:
                    logger.info(f"🔄 Перезапуск через {self.retry_delay} сек...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error("❌ Критическая ошибка, остановка воркера")
                    break

def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Robust GPT Worker')
    parser.add_argument('--batch-size', type=int, default=1, help='Размер батча')
    args = parser.parse_args()
    
    # Проверяем API ключ
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ Ошибка: OPENAI_API_KEY не найден в переменных окружения")
        sys.exit(1)
    
    print("🔑 API ключ: установлен")
    print("-" * 50)
    
    worker = RobustGPTWorker(batch_size=args.batch_size)
    worker.run()

if __name__ == "__main__":
    main()
