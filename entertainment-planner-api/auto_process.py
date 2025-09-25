#!/usr/bin/env python3
"""
Автоматический обработчик всех мест
Запускает полный цикл агентов без подтверждений
"""

import os
import sys
from datetime import datetime

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.places.orchestrator import auto_process_all_places

def main():
    """Главная функция автоматической обработки"""
    print("🤖 АВТОМАТИЧЕСКАЯ ОБРАБОТКА МЕСТ")
    print("=" * 50)
    print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # Запускаем автоматическую обработку
        result = auto_process_all_places()
        
        if result["success"]:
            print(f"\n🎉 УСПЕШНО ЗАВЕРШЕНО!")
            print(f"📊 Итоговая статистика:")
            print(f"  Всего мест: {result['total']}")
            print(f"  Обработано: {result['processed']}")
            print(f"  NEW → SUMMARIZED: {result['new_to_summarized']}")
            print(f"  SUMMARIZED → ENRICHED: {result['summarized_to_enriched']}")
            print(f"  ENRICHED → PUBLISHED: {result['enriched_to_published']}")
            print(f"  NEEDS_REVISION → PUBLISHED: {result['needs_revision_to_published']}")
            print(f"  Ошибок: {result['errors']}")
            print(f"  Неудачных: {result['failed']}")
        else:
            print(f"\n❌ ОШИБКА: {result.get('error', 'Неизвестная ошибка')}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print(f"\n⏹️ Обработка прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
