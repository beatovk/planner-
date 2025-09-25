#!/usr/bin/env python3
"""
Полная цепочка обработки данных:
1. Парсеры (TimeOut, BK Magazine)
2. GPT Саммаризатор
3. Google API Обогатитель
4. AI Editor Agent (финальная проверка)
"""

import os
import sys
import subprocess
import time
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_command(command: list, description: str) -> bool:
    """Запуск команды и проверка результата"""
    logger.info(f"🚀 {description}")
    logger.info(f"Команда: {' '.join(command)}")
    
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        logger.info(f"✅ {description} - успешно")
        if result.stdout:
            logger.info(f"Вывод: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ {description} - ошибка")
        logger.error(f"Код ошибки: {e.returncode}")
        if e.stdout:
            logger.error(f"Вывод: {e.stdout}")
        if e.stderr:
            logger.error(f"Ошибки: {e.stderr}")
        return False


def main():
    """Главная функция полной цепочки обработки"""
    logger.info("🎯 Запуск полной цепочки обработки данных")
    logger.info(f"Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Проверяем наличие API ключа
    if not os.getenv('OPENAI_API_KEY'):
        logger.error("❌ OPENAI_API_KEY не установлен!")
        sys.exit(1)
    
    # Список команд для выполнения
    commands = [
        {
            "command": ["python", "apps/places/commands/run_gpt_worker.py", "--batch-size", "10"],
            "description": "GPT Саммаризатор - обработка новых мест"
        },
        {
            "command": ["python", "apps/places/commands/enrich_google.py", "--batch-size", "20"],
            "description": "Google API Обогатитель - добавление координат и деталей"
        },
        {
            "command": ["python", "apps/places/commands/run_ai_editor.py", "--batch-size", "5"],
            "description": "AI Editor Agent - финальная проверка и дополнение"
        }
    ]
    
    # Выполняем команды последовательно
    success_count = 0
    total_commands = len(commands)
    
    for i, cmd_info in enumerate(commands, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"Этап {i}/{total_commands}: {cmd_info['description']}")
        logger.info(f"{'='*60}")
        
        if run_command(cmd_info['command'], cmd_info['description']):
            success_count += 1
            logger.info(f"✅ Этап {i} завершен успешно")
        else:
            logger.error(f"❌ Этап {i} завершен с ошибкой")
            # Можно продолжить выполнение или остановиться
            # logger.error("Останавливаем выполнение из-за ошибки")
            # break
        
        # Небольшая пауза между этапами
        if i < total_commands:
            logger.info("⏳ Пауза 5 секунд перед следующим этапом...")
            time.sleep(5)
    
    # Итоговая статистика
    logger.info(f"\n{'='*60}")
    logger.info("📊 ИТОГОВАЯ СТАТИСТИКА")
    logger.info(f"{'='*60}")
    logger.info(f"Всего этапов: {total_commands}")
    logger.info(f"Успешно выполнено: {success_count}")
    logger.info(f"Ошибок: {total_commands - success_count}")
    logger.info(f"Время завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if success_count == total_commands:
        logger.info("🎉 Все этапы выполнены успешно!")
        return 0
    else:
        logger.warning("⚠️ Некоторые этапы завершились с ошибками")
        return 1


def run_individual_stage(stage: str):
    """Запуск отдельного этапа"""
    stages = {
        "gpt": {
            "command": ["python", "apps/places/commands/run_gpt_worker.py", "--batch-size", "10"],
            "description": "GPT Саммаризатор"
        },
        "google": {
            "command": ["python", "apps/places/commands/enrich_google.py", "--batch-size", "20"],
            "description": "Google API Обогатитель"
        },
        "ai_editor": {
            "command": ["python", "apps/places/commands/run_ai_editor.py", "--batch-size", "5"],
            "description": "AI Editor Agent"
        }
    }
    
    if stage not in stages:
        logger.error(f"❌ Неизвестный этап: {stage}")
        logger.error(f"Доступные этапы: {', '.join(stages.keys())}")
        return 1
    
    cmd_info = stages[stage]
    logger.info(f"🎯 Запуск этапа: {cmd_info['description']}")
    
    if run_command(cmd_info['command'], cmd_info['description']):
        logger.info("✅ Этап завершен успешно")
        return 0
    else:
        logger.error("❌ Этап завершен с ошибкой")
        return 1


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Полная цепочка обработки данных')
    parser.add_argument('--stage', choices=['gpt', 'google', 'ai_editor'], 
                       help='Запустить только определенный этап')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Подробное логирование')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.stage:
        # Запуск отдельного этапа
        exit_code = run_individual_stage(args.stage)
    else:
        # Запуск полной цепочки
        exit_code = main()
    
    sys.exit(exit_code)
