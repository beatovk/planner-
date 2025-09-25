#!/usr/bin/env python3
"""
Команда для валидации словаря синонимов.
Использование: python -m apps.places.commands.validate_synonyms [--fix]
"""

import argparse
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from apps.places.services.synonyms_validator import validate_synonyms, get_synonyms_health


def main():
    parser = argparse.ArgumentParser(description="Валидация словаря синонимов")
    parser.add_argument("--fix", action="store_true", help="Попытаться исправить найденные проблемы")
    parser.add_argument("--health", action="store_true", help="Показать health метрики")
    parser.add_argument("--verbose", "-v", action="store_true", help="Подробный вывод")
    
    args = parser.parse_args()
    
    if args.health:
        # Показываем health метрики
        metrics = get_synonyms_health()
        
        print("🔍 Health метрики словаря синонимов:")
        print(f"   - Здоров: {'✅' if metrics['is_healthy'] else '❌'}")
        print(f"   - Слотов: {metrics['total_slots']}")
        print(f"   - Expands: {metrics['total_expands']}")
        print(f"   - Невалидных тегов: {metrics['invalid_tags']}")
        print(f"   - Дубликатов синонимов: {metrics['duplicate_synonyms']}")
        print(f"   - Отсутствующих canonical: {metrics['missing_canonicals']}")
        print(f"   - Валидных тегов в онтологии: {metrics['valid_tags_count']}")
        
        if args.verbose and metrics['warnings']:
            print("\n⚠️ Предупреждения:")
            for warning in metrics['warnings'][:10]:
                print(f"   - {warning}")
            if len(metrics['warnings']) > 10:
                print(f"   ... и еще {len(metrics['warnings']) - 10}")
        
        if args.verbose and metrics['errors']:
            print("\n❌ Ошибки:")
            for error in metrics['errors']:
                print(f"   - {error}")
        
        return 0 if metrics['is_healthy'] else 1
    
    else:
        # Выполняем валидацию
        result = validate_synonyms()
        
        print("🔍 Валидация словаря синонимов:")
        print(f"   - Валиден: {'✅' if result.is_valid else '❌'}")
        print(f"   - Слотов: {result.stats['total_slots']}")
        print(f"   - Expands: {result.stats['total_expands']}")
        print(f"   - Ошибок: {len(result.errors)}")
        print(f"   - Предупреждений: {len(result.warnings)}")
        
        if result.errors:
            print("\n❌ Ошибки:")
            for error in result.errors:
                print(f"   - {error}")
        
        if args.verbose and result.warnings:
            print("\n⚠️ Предупреждения:")
            for warning in result.warnings[:20]:
                print(f"   - {warning}")
            if len(result.warnings) > 20:
                print(f"   ... и еще {len(result.warnings) - 20}")
        
        if args.fix and result.errors:
            print("\n🔧 Попытка исправления ошибок...")
            # Здесь можно добавить логику автоматического исправления
            print("   - Автоматическое исправление пока не реализовано")
        
        return 0 if result.is_valid else 1


if __name__ == "__main__":
    sys.exit(main())
