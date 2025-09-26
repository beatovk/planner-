#!/usr/bin/env python3
"""
Slotter - извлечение слотов из свободного текста запроса.
Использует CANON_SLOTS для маппинга запросов на структурированные слоты.
"""

import re
import time
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from apps.places.schemas.slots import (
    Slot, SlotType, SlotMatch, SlotterResult, SlotterConfig,
    QueryToken, SynonymEntry, SlotterMetrics, create_slot, create_slot_match,
    create_slotter_result, create_query_token, create_synonym_entry
)

logger = logging.getLogger(__name__)


class Slotter:
    """Слоттер для извлечения слотов из свободного текста."""
    
    def __init__(self, config: Optional[SlotterConfig] = None):
        self.config = config or SlotterConfig()
        self.metrics = SlotterMetrics()
        self._load_canon_slots()
        self._load_synonyms()
    
    def _load_canon_slots(self):
        """Загружает CANON_SLOTS из конфигурации."""
        try:
            from config.canon_slots import CANON_SLOTS
            self.canon_slots = CANON_SLOTS
        except ImportError:
            logger.warning("CANON_SLOTS not found, using empty slots")
            self.canon_slots = {}
    
    def _load_synonyms(self):
        """Загружает синонимы из конфигурации."""
        try:
            import os, yaml
            path = os.path.join(os.getcwd(), "config", "synonyms.yml")
            if os.path.exists(path):
                cfg = yaml.safe_load(open(path, "r", encoding="utf-8"))
                self.synonyms = cfg.get("synonyms", {})
            else:
                self.synonyms = {}
        except Exception as e:
            logger.warning(f"Failed to load synonyms: {e}")
            self.synonyms = {}
    
    def extract_slots(self, query: str) -> SlotterResult:
        """Извлекает слоты из запроса."""
        start_time = time.time()
        
        if not query or not query.strip():
            return create_slotter_result([], False, None, 0.0, {"query": query})
        
        query = query.strip()
        tokens = self._tokenize_query(query)
        
        # Извлекаем слоты
        slots = []
        used_tokens = set()
        
        # 1. Точные совпадения
        for token in tokens:
            if token.text in used_tokens:
                continue
                
            slot = self._match_exact_token(token)
            if slot:
                slots.append(slot)
                used_tokens.add(token.text)
        
        # 2. Фразовые совпадения
        for i, token in enumerate(tokens):
            if token.text in used_tokens:
                continue
                
            # Проверяем фразы из 2-3 токенов
            for length in [2, 3]:
                if i + length <= len(tokens):
                    phrase_tokens = tokens[i:i+length]
                    phrase_text = " ".join([t.text for t in phrase_tokens])
                    
                    if phrase_text in used_tokens:
                        continue
                    
                    slot = self._match_phrase(phrase_text, phrase_tokens)
                    if slot:
                        slots.append(slot)
                        used_tokens.add(phrase_text)
                        # Помечаем использованные токены
                        for t in phrase_tokens:
                            used_tokens.add(t.text)
                        break
        
        # 3. Нечеткие совпадения (если включены)
        if self.config.enable_fuzzy:
            for token in tokens:
                if token.text in used_tokens:
                    continue
                    
                slot = self._match_fuzzy_token(token)
                if slot and slot.confidence >= self.config.fuzzy_threshold:
                    slots.append(slot)
                    used_tokens.add(token.text)
        
        # 4. Fallback (если нужно)
        fallback_used = False
        fallback_reason = None
        
        if len(slots) == 0 and self.config.enable_fallback:
            fallback_slots = self._fallback_extraction(query, tokens)
            if fallback_slots:
                slots.extend(fallback_slots)
                fallback_used = True
                fallback_reason = "no_matches_found"
        
        # Ограничиваем количество слотов
        slots = slots[:self.config.max_slots]
        
        # Фильтруем по минимальной уверенности
        slots = [s for s in slots if s.confidence >= self.config.min_confidence]
        
        processing_time = (time.time() - start_time) * 1000
        
        # Обновляем метрики
        self._update_metrics(len(slots) > 0, fallback_used, processing_time, len(slots))
        
        return create_slotter_result(
            slots=slots,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            processing_time_ms=processing_time,
            debug_info={
                "query": query,
                "tokens": [t.text for t in tokens],
                "used_tokens": list(used_tokens),
                "canon_slots_checked": len(self.canon_slots)
            }
        )
    
    def _tokenize_query(self, query: str) -> List[QueryToken]:
        """Токенизирует запрос."""
        # Простая токенизация по пробелам и знакам препинания
        tokens = []
        words = re.findall(r'\b\w+\b', query.lower())
        
        for i, word in enumerate(words):
            tokens.append(create_query_token(
                text=word,
                position=i,
                length=len(word),
                is_unigram=True
            ))
        
        return tokens
    
    def _match_exact_token(self, token: QueryToken) -> Optional[Slot]:
        """Ищет точное совпадение токена."""
        if token.text in self.canon_slots:
            return self._create_slot_from_canon(token.text, token.text, "exact", 1.0, token)
        
        # Проверяем синонимы
        for canon_key, slot_config in self.canon_slots.items():
            if token.text in slot_config.get("synonyms", []):
                return self._create_slot_from_canon(canon_key, token.text, "exact", 0.9, token)
        
        return None
    
    def _match_phrase(self, phrase: str, tokens: List[QueryToken]) -> Optional[Slot]:
        """Ищет фразовое совпадение."""
        if phrase in self.canon_slots:
            return self._create_slot_from_canon(phrase, phrase, "phrase", 1.0, tokens[0])
        
        # Проверяем синонимы
        for canon_key, slot_config in self.canon_slots.items():
            if phrase in slot_config.get("synonyms", []):
                return self._create_slot_from_canon(canon_key, phrase, "phrase", 0.9, tokens[0])
        
        return None
    
    def _match_fuzzy_token(self, token: QueryToken) -> Optional[Slot]:
        """Ищет нечеткое совпадение токена."""
        best_match = None
        best_score = 0.0
        
        for canon_key, slot_config in self.canon_slots.items():
            # Проверяем расстояние Левенштейна
            score = self._levenshtein_similarity(token.text, canon_key)
            if score > best_score and score >= self.config.fuzzy_threshold:
                best_score = score
                best_match = canon_key
        
        if best_match:
            return self._create_slot_from_canon(best_match, token.text, "fuzzy", best_score, token)
        
        return None
    
    def _create_slot_from_canon(self, canon_key: str, matched_text: str, match_type: str, 
                               confidence: float, token: QueryToken) -> Slot:
        """Создает слот из CANON_SLOTS записи."""
        slot_config = self.canon_slots[canon_key]
        
        # Определяем тип слота
        slot_type = SlotType(slot_config.get("kind", "experience"))
        
        # Создаем фильтры
        filters = {
            "include_tags": slot_config.get("include_tags", []),
            "include_categories": slot_config.get("include_categories", []),
            "exclude_categories": slot_config.get("exclude_categories", [])
        }
        
        return create_slot(
            type=slot_type,
            canonical=canon_key,
            label=canon_key.replace("_", " ").title(),
            confidence=confidence,
            filters=filters,
            matched_text=matched_text,
            reason=f"{match_type}_match",
            context={"match_type": match_type, "position": token.position}
        )
    
    def _fallback_extraction(self, query: str, tokens: List[QueryToken]) -> List[Slot]:
        """Fallback извлечение слотов."""
        slots = []
        
        # Простой fallback по ключевым словам
        query_lower = query.lower()
        
        # Проверяем vibe ключевые слова
        vibe_keywords = {
            "chill": "chill",
            "romantic": "romantic", 
            "lively": "lively",
            "artsy": "artsy",
            "premium": "premium",
            "nature": "nature",
            "family": "family",
            "active": "active",
            "hidden": "hidden_gem",
            "instagram": "instagrammable"
        }
        
        for keyword, canon_key in vibe_keywords.items():
            if keyword in query_lower and canon_key in self.canon_slots:
                slot = self._create_slot_from_canon(canon_key, keyword, "fallback", 0.5, tokens[0])
                slots.append(slot)
                break
        
        return slots
    
    def _levenshtein_similarity(self, s1: str, s2: str) -> float:
        """Вычисляет схожесть по расстоянию Левенштейна."""
        if len(s1) < len(s2):
            return self._levenshtein_similarity(s2, s1)
        
        if len(s2) == 0:
            return 0.0
        
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        max_len = max(len(s1), len(s2))
        return 1.0 - (previous_row[-1] / max_len)
    
    def _update_metrics(self, success: bool, fallback_used: bool, processing_time: float, slots_count: int):
        """Обновляет метрики."""
        self.metrics.total_queries += 1
        if success:
            self.metrics.successful_matches += 1
        if fallback_used:
            self.metrics.fallback_used += 1
        
        # Обновляем средние значения
        total = self.metrics.total_queries
        self.metrics.avg_processing_time_ms = (
            (self.metrics.avg_processing_time_ms * (total - 1) + processing_time) / total
        )
        self.metrics.avg_slots_per_query = (
            (self.metrics.avg_slots_per_query * (total - 1) + slots_count) / total
        )
    
    def get_metrics(self) -> SlotterMetrics:
        """Возвращает метрики слоттера."""
        return self.metrics
    
    def reset_metrics(self):
        """Сбрасывает метрики."""
        self.metrics = SlotterMetrics()


def create_slotter(config: Optional[SlotterConfig] = None) -> Slotter:
    """Создает экземпляр слоттера."""
    return Slotter(config)
