#!/usr/bin/env python3
"""
Тестовый скрипт для AI Editor Agent
"""

import os
import sys
import logging

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.places.workers.ai_editor import AIEditorAgent
from apps.places.workers.web_verifier import WebVerifier

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_web_verifier():
    """Тестирование WebVerifier"""
    logger.info("🔍 Тестирование WebVerifier...")
    
    verifier = WebVerifier()
    
    # Тестовые данные
    test_cases = [
        {
            "name": "Sirocco Sky Bar",
            "category": "Bar",
            "address": "Lebua at State Tower, Bangkok"
        },
        {
            "name": "Vertigo and Moon Bar",
            "category": "Bar", 
            "address": "Banyan Tree Bangkok"
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        logger.info(f"\n--- Тест {i}: {case['name']} ---")
        
        # Проверяем достоверность
        verification = verifier.verify_place_data(
            case["name"],
            case["category"],
            case["address"]
        )
        
        logger.info(f"Результат верификации: {verification}")
        
        # Ищем изображения
        images = verifier.search_quality_images(
            case["name"],
            case["category"]
        )
        
        logger.info(f"Найдено изображений: {len(images)}")
        for j, img in enumerate(images[:3], 1):
            logger.info(f"  {j}. {img}")


def test_ai_editor_agent():
    """Тестирование AI Editor Agent"""
    logger.info("\n🤖 Тестирование AI Editor Agent...")
    
    # Проверяем наличие API ключа
    if not os.getenv('OPENAI_API_KEY'):
        logger.error("❌ OPENAI_API_KEY не установлен!")
        return False
    
    try:
        agent = AIEditorAgent(batch_size=2)
        
        logger.info("✅ AI Editor Agent создан успешно")
        logger.info(f"📊 Размер батча: {agent.batch_size}")
        logger.info(f"🔑 API ключ: {'установлен' if os.getenv('OPENAI_API_KEY') else 'НЕ НАЙДЕН'}")
        
        # Запускаем обработку (только 2 места для теста)
        logger.info("🚀 Запуск обработки...")
        agent.run()
        
        logger.info("✅ AI Editor Agent завершил работу успешно!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка AI Editor Agent: {e}")
        return False


def main():
    """Главная функция тестирования"""
    logger.info("🎯 Запуск тестирования AI Editor Agent")
    logger.info("=" * 60)
    
    # Тест 1: WebVerifier
    try:
        test_web_verifier()
        logger.info("✅ WebVerifier тест пройден")
    except Exception as e:
        logger.error(f"❌ WebVerifier тест провален: {e}")
    
    # Тест 2: AI Editor Agent
    try:
        success = test_ai_editor_agent()
        if success:
            logger.info("✅ AI Editor Agent тест пройден")
        else:
            logger.error("❌ AI Editor Agent тест провален")
    except Exception as e:
        logger.error(f"❌ AI Editor Agent тест провален: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info("🏁 Тестирование завершено")


if __name__ == "__main__":
    main()
