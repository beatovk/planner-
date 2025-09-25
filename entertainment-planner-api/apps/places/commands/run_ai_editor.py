#!/usr/bin/env python3
"""Команда для запуска AI Editor Agent"""

import sys
import os
import argparse
import logging

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from apps.places.workers.ai_editor import AIEditorAgent


def main():
    parser = argparse.ArgumentParser(description='AI Editor Agent - финальная проверка и дополнение данных')
    parser.add_argument('--batch-size', type=int, default=5, help='Размер батча для обработки')
    parser.add_argument('--api-key', type=str, help='OpenAI API ключ (или через OPENAI_API_KEY env)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Подробное логирование')
    
    args = parser.parse_args()
    
    # Настройка логирования
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Установка API ключа
    if args.api_key:
        os.environ['OPENAI_API_KEY'] = args.api_key
    
    try:
        # Создание и запуск AI Editor Agent
        agent = AIEditorAgent(
            batch_size=args.batch_size,
            api_key=args.api_key
        )
        
        print("🤖 Запуск AI Editor Agent...")
        print(f"📊 Размер батча: {args.batch_size}")
        print(f"🔑 API ключ: {'установлен' if os.getenv('OPENAI_API_KEY') else 'НЕ НАЙДЕН'}")
        print("🔍 Функции:")
        print("  - Проверка достоверности данных через веб-поиск")
        print("  - Поиск качественных изображений")
        print("  - Дополнение недостающих полей")
        print("  - Финальная верификация через GPT")
        print("-" * 50)
        
        agent.run()
        
        print("-" * 50)
        print("✅ AI Editor Agent завершил работу успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
