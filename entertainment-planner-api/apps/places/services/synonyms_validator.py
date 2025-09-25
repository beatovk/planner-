"""
Валидатор словаря синонимов для слоттера.
Проверяет совместимость config/synonyms.yml с существующей онтологией.
"""

import yaml
import os
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Результат валидации словаря синонимов."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    stats: Dict[str, Any]


class SynonymsValidator:
    """Валидатор словаря синонимов."""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.valid_tags: Set[str] = set()
        self.additional_prefixes = ['cuisine:', 'drink:', 'area:', 'diet:']
        
    def load_ontology_tags(self) -> None:
        """Загружает все валидные теги из онтологии."""
        try:
            # Загружаем vibes.yml
            vibes_path = self.config_dir / "vibes.yml"
            if vibes_path.exists():
                with open(vibes_path, 'r', encoding='utf-8') as f:
                    vibes_config = yaml.safe_load(f)
                
                # Vibes
                for vibe in vibes_config.get('vibes', []):
                    self.valid_tags.add(f"vibe:{vibe['id']}")
                
                # Scenarios  
                for scenario in vibes_config.get('scenarios', []):
                    self.valid_tags.add(f"scenario:{scenario['id']}")
                
                # Experiences
                for exp in vibes_config.get('experiences', []):
                    self.valid_tags.add(f"experience:{exp['id']}")
                
                # Food/Drink modifiers
                for mod in vibes_config.get('food_drink_modifiers', []):
                    self.valid_tags.add(f"food_drink:{mod['id']}")
                
                # Operational flags
                for flag in vibes_config.get('operational_flags', []):
                    self.valid_tags.add(f"feature:{flag['id']}")
                
                # Price tiers
                for tier in vibes_config.get('price_tiers', []):
                    self.valid_tags.add(f"price:{tier['id']}")
                
                # Noise levels
                for noise in vibes_config.get('noise_levels', []):
                    self.valid_tags.add(f"noise:{noise['id']}")
                
                # Lighting
                for light in vibes_config.get('lighting', []):
                    self.valid_tags.add(f"lighting:{light['id']}")
                
                # Seating
                for seat in vibes_config.get('seating', []):
                    self.valid_tags.add(f"seating:{seat['id']}")
                
                # Views
                for view in vibes_config.get('views', []):
                    self.valid_tags.add(f"view:{view['id']}")
            
            # Загружаем dish_to_cuisine.yml
            dish_path = self.config_dir / "dish_to_cuisine.yml"
            if dish_path.exists():
                with open(dish_path, 'r', encoding='utf-8') as f:
                    dish_config = yaml.safe_load(f)
                
                # Добавляем dish теги
                for dish in dish_config:
                    self.valid_tags.add(f"dish:{dish}")
            
            logger.info(f"Loaded {len(self.valid_tags)} valid tags from ontology")
            
        except Exception as e:
            logger.error(f"Failed to load ontology tags: {e}")
            raise
    
    def validate_synonyms_config(self) -> ValidationResult:
        """Валидирует config/synonyms.yml."""
        errors = []
        warnings = []
        stats = {
            'total_slots': 0,
            'total_expands': 0,
            'invalid_tags': 0,
            'duplicate_synonyms': 0,
            'missing_canonicals': 0
        }
        
        try:
            # Загружаем synonyms.yml
            synonyms_path = self.config_dir / "synonyms.yml"
            if not synonyms_path.exists():
                errors.append(f"synonyms.yml not found at {synonyms_path}")
                return ValidationResult(False, errors, warnings, stats)
            
            with open(synonyms_path, 'r', encoding='utf-8') as f:
                synonyms_config = yaml.safe_load(f)
            
            # Проверяем структуру
            if 'slots' not in synonyms_config:
                errors.append("Missing 'slots' key in synonyms.yml")
                return ValidationResult(False, errors, warnings, stats)
            
            slots = synonyms_config['slots']
            if not isinstance(slots, list):
                errors.append("'slots' must be a list")
                return ValidationResult(False, errors, warnings, stats)
            
            stats['total_slots'] = len(slots)
            
            # Собираем все синонимы для проверки дубликатов
            all_synonyms = {}
            
            for i, slot in enumerate(slots):
                if not isinstance(slot, dict):
                    errors.append(f"Slot {i} is not a dictionary")
                    continue
                
                # Проверяем обязательные поля
                required_fields = ['type', 'canonical', 'synonyms', 'expands_to_tags']
                for field in required_fields:
                    if field not in slot:
                        errors.append(f"Slot {i} missing required field '{field}'")
                        continue
                
                canonical = slot.get('canonical')
                synonyms = slot.get('synonyms', [])
                expands_to_tags = slot.get('expands_to_tags', [])
                
                stats['total_expands'] += len(expands_to_tags)
                
                # Проверяем expands_to_tags
                for tag in expands_to_tags:
                    if not self._is_valid_tag(tag):
                        errors.append(f"Slot '{canonical}' has invalid tag: {tag}")
                        stats['invalid_tags'] += 1
                
                # Проверяем дубликаты синонимов
                for synonym in synonyms:
                    if synonym in all_synonyms:
                        warnings.append(f"Duplicate synonym '{synonym}' in slots '{all_synonyms[synonym]}' and '{canonical}'")
                        stats['duplicate_synonyms'] += 1
                    else:
                        all_synonyms[synonym] = canonical
                
                # Проверяем canonical в онтологии
                if not self._is_canonical_valid(slot):
                    warnings.append(f"Canonical '{canonical}' not found in ontology")
                    stats['missing_canonicals'] += 1
            
            is_valid = len(errors) == 0
            
            return ValidationResult(is_valid, errors, warnings, stats)
            
        except Exception as e:
            errors.append(f"Failed to validate synonyms config: {e}")
            return ValidationResult(False, errors, warnings, stats)
    
    def _is_valid_tag(self, tag: str) -> bool:
        """Проверяет, является ли тег валидным."""
        # Проверяем точное совпадение с онтологией
        if tag in self.valid_tags:
            return True
        
        # Проверяем дополнительные префиксы
        for prefix in self.additional_prefixes:
            if tag.startswith(prefix):
                return True
        
        return False
    
    def _is_canonical_valid(self, slot: Dict[str, Any]) -> bool:
        """Проверяет, существует ли canonical в онтологии."""
        canonical = slot.get('canonical')
        slot_type = slot.get('type')
        
        if not canonical or not slot_type:
            return False
        
        # Проверяем разные типы canonical
        if slot_type == 'vibe':
            return f"vibe:{canonical}" in self.valid_tags
        elif slot_type == 'experience':
            return f"experience:{canonical}" in self.valid_tags
        elif slot_type == 'drink':
            return f"drink:{canonical}" in self.valid_tags
        elif slot_type == 'cuisine':
            return f"cuisine:{canonical}" in self.valid_tags
        elif slot_type == 'dish':
            return f"dish:{canonical}" in self.valid_tags
        elif slot_type == 'area':
            return f"area:{canonical}" in self.valid_tags
        
        return False
    
    def validate(self) -> ValidationResult:
        """Выполняет полную валидацию словаря синонимов."""
        self.load_ontology_tags()
        return self.validate_synonyms_config()
    
    def get_health_metrics(self) -> Dict[str, Any]:
        """Возвращает метрики здоровья словаря для health endpoint."""
        result = self.validate()
        
        return {
            'is_healthy': result.is_valid,
            'total_slots': result.stats['total_slots'],
            'total_expands': result.stats['total_expands'],
            'invalid_tags': result.stats['invalid_tags'],
            'duplicate_synonyms': result.stats['duplicate_synonyms'],
            'missing_canonicals': result.stats['missing_canonicals'],
            'errors': result.errors,
            'warnings': result.warnings,
            'valid_tags_count': len(self.valid_tags)
        }


def validate_synonyms() -> ValidationResult:
    """Удобная функция для валидации словаря синонимов."""
    validator = SynonymsValidator()
    return validator.validate()


def get_synonyms_health() -> Dict[str, Any]:
    """Удобная функция для получения метрик здоровья словаря."""
    validator = SynonymsValidator()
    return validator.get_health_metrics()


if __name__ == "__main__":
    # Тестирование валидатора
    result = validate_synonyms()
    
    print("🔍 Результат валидации словаря синонимов:")
    print(f"   - Валиден: {'✅' if result.is_valid else '❌'}")
    print(f"   - Слотов: {result.stats['total_slots']}")
    print(f"   - Expands: {result.stats['total_expands']}")
    print(f"   - Ошибок: {len(result.errors)}")
    print(f"   - Предупреждений: {len(result.warnings)}")
    
    if result.errors:
        print("\n❌ Ошибки:")
        for error in result.errors[:5]:
            print(f"   - {error}")
        if len(result.errors) > 5:
            print(f"   ... и еще {len(result.errors) - 5}")
    
    if result.warnings:
        print("\n⚠️ Предупреждения:")
        for warning in result.warnings[:5]:
            print(f"   - {warning}")
        if len(result.warnings) > 5:
            print(f"   ... и еще {len(result.warnings) - 5}")
