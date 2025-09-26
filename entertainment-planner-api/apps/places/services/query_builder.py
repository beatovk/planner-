"""
QueryBuilder - сервис для построения запросов и извлечения слотов.
"""

import re
import time
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from pathlib import Path
import yaml

from apps.places.schemas.slots import (
    Slot, SlotType, SlotMatch, SlotterResult, SlotterConfig,
    QueryToken, SynonymEntry, SlotterMetrics,
    create_slot, create_slot_match, create_slotter_result,
    create_query_token, create_synonym_entry
)

logger = logging.getLogger(__name__)


class QueryBuilder:
    """Строитель запросов с извлечением слотов."""
    
    def __init__(self, config: SlotterConfig = None):
        self.config = config or SlotterConfig()
        self.synonyms: Dict[str, SynonymEntry] = {}
        self.metrics = SlotterMetrics()
        self._load_synonyms()
    
    def _load_synonyms(self) -> None:
        """Загружает словарь синонимов из config/synonyms.yml."""
        try:
            config_path = Path("config/synonyms.yml")
            if not config_path.exists():
                logger.error("synonyms.yml not found")
                return
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            for slot_data in config.get('slots', []):
                try:
                    entry = create_synonym_entry(
                        type=SlotType(slot_data['type']),
                        canonical=slot_data['canonical'],
                        synonyms=slot_data['synonyms'],
                        expands_to_tags=slot_data['expands_to_tags'],
                        denylist=slot_data.get('denylist')
                    )
                    
                    # Индексируем по синонимам
                    for synonym in entry.synonyms:
                        self.synonyms[synonym.lower()] = entry
                    
                    # Индексируем по canonical
                    self.synonyms[entry.canonical.lower()] = entry
                    
                except Exception as e:
                    logger.warning(f"Failed to load slot {slot_data.get('canonical', 'unknown')}: {e}")
            
            logger.info(f"Loaded {len(self.synonyms)} synonym entries")
            
        except Exception as e:
            logger.error(f"Failed to load synonyms: {e}")
            raise
    
    def build_slots(self, query: str) -> SlotterResult:
        """Извлекает слоты из запроса."""
        start_time = time.time()
        
        try:
            logger.debug(f"Building slots for query: '{query}'")
            
            # Токенизация запроса
            tokens = self._tokenize_query(query)
            logger.debug(f"Tokenized query into {len(tokens)} tokens: {[t.text for t in tokens]}")
            
            # Извлечение слотов
            slot_matches = self._extract_slots(tokens)
            logger.debug(f"Extracted {len(slot_matches)} slot matches")
            
            # Сортировка по confidence и позиции
            slot_matches.sort(key=lambda x: (-x.confidence, x.position))
            
            # Ограничение количества слотов
            slot_matches = slot_matches[:self.config.max_slots]
            logger.debug(f"Limited to {len(slot_matches)} slots after max_slots filter")
            
            # Создание слотов
            slots = []
            for match in slot_matches:
                slot = self._create_slot_from_match(match)
                slots.append(slot)
                logger.debug(f"Created slot: {slot.type}:{slot.canonical} (confidence: {slot.confidence:.2f})")

            # Контекст: если среди слотов есть блюдо — помечаем всем has_dish=True
            try:
                has_dish = any(s.type == SlotType.DISH for s in slots)
                if has_dish:
                    for s in slots:
                        # Slot.context гарантирован по create_slot
                        s.context["has_dish"] = True
            except Exception:
                pass
            
            # Fallback если слотов недостаточно
            fallback_used = False
            fallback_reason = None
            
            if len(slots) < 3 and self.config.enable_fallback:
                logger.debug(f"Applying fallback strategies for {3 - len(slots)} missing slots")
                fallback_slots = self._apply_fallback_strategies(query, slots)
                slots.extend(fallback_slots)
                fallback_used = True
                fallback_reason = f"Added {len(fallback_slots)} fallback slots"
                logger.debug(f"Added {len(fallback_slots)} fallback slots: {[s.canonical for s in fallback_slots]}")
            
            processing_time = (time.time() - start_time) * 1000
            
            # Обновление метрик
            self._update_metrics(len(slots), fallback_used, processing_time)
            
            logger.info(f"Built {len(slots)} slots for query '{query}' in {processing_time:.2f}ms")
            
            return create_slotter_result(
                slots=slots,
                fallback_used=fallback_used,
                fallback_reason=fallback_reason,
                processing_time_ms=processing_time,
                debug_info={
                    'tokens': [t.text for t in tokens],
                    'matches': len(slot_matches),
                    'fallback_slots': len(slots) - len(slot_matches),
                    'slot_types': [s.type.value for s in slots],
                    'confidences': [s.confidence for s in slots]
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to build slots for query '{query}': {e}")
            return create_slotter_result(
                slots=[],
                fallback_used=False,
                processing_time_ms=(time.time() - start_time) * 1000,
                debug_info={'error': str(e)}
            )
    
    def _tokenize_query(self, query: str) -> List[QueryToken]:
        """Токенизирует запрос на фразы, многословные и однословные токены."""
        tokens = []
        query_lower = query.lower().strip()
        
        # Разбиваем на слова
        words = re.findall(r'\b\w+\b', query_lower)
        
        # Создаем токены разной длины
        for i, word in enumerate(words):
            # Однословный токен
            tokens.append(create_query_token(
                text=word,
                position=i,
                length=1,
                is_unigram=True
            ))
            
            # Многословные токены (2-3 слова)
            for length in [2, 3]:
                if i + length <= len(words):
                    phrase = ' '.join(words[i:i+length])
                    tokens.append(create_query_token(
                        text=phrase,
                        position=i,
                        length=length,
                        is_multiword=True
                    ))
        
        # Фразовые токены (4+ слов)
        for length in range(4, len(words) + 1):
            for i in range(len(words) - length + 1):
                phrase = ' '.join(words[i:i+length])
                tokens.append(create_query_token(
                    text=phrase,
                    position=i,
                    length=length,
                    is_phrase=True
                ))
        
        return tokens
    
    def _extract_slots(self, tokens: List[QueryToken]) -> List[SlotMatch]:
        """Извлекает слоты из токенов."""
        matches = []
        used_positions = set()
        
        # Приоритизация: phrase > multiword > unigram
        for token in sorted(tokens, key=lambda t: (-t.length, t.position)):
            if token.position in used_positions:
                continue
            
            # Поиск точного совпадения
            if token.text in self.synonyms:
                entry = self.synonyms[token.text]
                
                # Проверка denylist
                if entry.is_denied(token.text):
                    continue
                
                # Создание матча
                match = self._create_slot_match(entry, token, "exact")
                matches.append(match)
                used_positions.update(range(token.position, token.position + token.length))
                continue
            
            # Fuzzy matching если включен
            if self.config.enable_fuzzy:
                fuzzy_match = self._find_fuzzy_match(token)
                if fuzzy_match:
                    matches.append(fuzzy_match)
                    used_positions.update(range(token.position, token.position + token.length))
        
        return matches
    
    def _find_fuzzy_match(self, token: QueryToken) -> Optional[SlotMatch]:
        """Находит fuzzy совпадение для токена."""
        # Простая реализация fuzzy matching
        # В реальной системе можно использовать pg_trgm/unaccent
        
        best_match = None
        best_score = 0.0
        
        for synonym, entry in self.synonyms.items():
            # Проверка denylist
            if entry.is_denied(token.text):
                continue
            
            # Простой алгоритм схожести
            score = self._calculate_similarity(token.text, synonym)
            
            if score >= self.config.fuzzy_threshold and score > best_score:
                best_score = score
                best_match = self._create_slot_match(entry, token, "fuzzy", score)
        
        return best_match
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Вычисляет схожесть между двумя строками."""
        # Простая реализация Jaccard similarity
        set1 = set(text1.lower())
        set2 = set(text2.lower())
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    def _create_slot_match(self, entry: SynonymEntry, token: QueryToken, match_type: str, confidence: float = None) -> SlotMatch:
        """Создает результат матчинга слота."""
        if confidence is None:
            # Базовый confidence на основе типа матча
            confidence_map = {
                "exact": 1.0,
                "phrase": 0.9,
                "multiword": 0.8,
                "unigram": 0.7,
                "fuzzy": 0.6
            }
            confidence = confidence_map.get(match_type, 0.5)
        
        # Создаем слот
        slot = create_slot(
            type=entry.type,
            canonical=entry.canonical,
            label=entry.canonical.replace('_', ' ').title(),
            confidence=confidence,
            filters={'expands_to_tags': entry.expands_to_tags},
            matched_text=token.text,
            reason=f"matched {entry.type}:{entry.canonical}"
        )
        
        return create_slot_match(
            slot=slot,
            matched_synonym=token.text,
            match_type=match_type,
            confidence=confidence,
            position=token.position
        )
    
    def _create_slot_from_match(self, match: SlotMatch) -> Slot:
        """Создает слот из результата матчинга."""
        return match.slot
    
    def _apply_fallback_strategies(self, query: str, existing_slots: List[Slot]) -> List[Slot]:
        """Применяет fallback стратегии для добавления слотов."""
        high_conf_slots = [slot for slot in existing_slots if slot.confidence >= 0.8]
        if high_conf_slots:
            token_count = len(self._tokenize_query(query))
            # Не подмешиваем общий fallback, если пользователь явно сформулировал один или два уверенных интента
            if token_count <= 5:
                return []

        fallback_slots = []
        
        for strategy in self.config.fallback_strategies:
            if strategy == "signals:editorial":
                # Добавляем слот на основе editorial signals
                slot = self._create_editorial_fallback_slot(query)
                if slot:
                    fallback_slots.append(slot)
            
            elif strategy == "co-occurrence":
                # Добавляем слот на основе co-occurrence
                slot = self._create_cooccurrence_fallback_slot(query)
                if slot:
                    fallback_slots.append(slot)
            
            # Ограничиваем количество fallback слотов
            if len(fallback_slots) >= 3 - len(existing_slots):
                break
        
        return fallback_slots
    
    def _create_editorial_fallback_slot(self, query: str) -> Optional[Slot]:
        """Создает fallback слот на основе editorial signals."""
        query_lower = query.lower()

        # Анализируем ключевые слова для определения типа опыта
        if any(word in query_lower for word in ['date', 'dating', 'romantic', 'anniversary', 'proposal']):
            return create_slot(
                type=SlotType.VIBE,
                canonical="romantic",
                label="Romantic",
                confidence=0.3,
                filters={'expands_to_tags': ['vibe:romantic', 'scenario:date']},
                matched_text=query,
                reason="fallback:editorial_romantic"
            )
        if any(word in query_lower for word in ['food', 'eat', 'restaurant', 'dinner', 'lunch']):
            return create_slot(
                type=SlotType.CUISINE,
                canonical="thai",
                label="Thai Cuisine",
                confidence=0.3,
                filters={'expands_to_tags': ['cuisine:thai']},
                matched_text=query,
                reason="fallback:editorial_food"
            )
        elif any(word in query_lower for word in ['drink', 'wine', 'coffee', 'tea', 'bar']):
            return create_slot(
                type=SlotType.DRINK,
                canonical="specialty_coffee",
                label="Specialty Coffee",
                confidence=0.3,
                filters={'expands_to_tags': ['drink:specialty_coffee']},
                matched_text=query,
                reason="fallback:editorial_drink"
            )
        elif any(word in query_lower for word in ['view', 'rooftop', 'skyline', 'scenic']):
            return create_slot(
                type=SlotType.EXPERIENCE,
                canonical="rooftop",
                label="Rooftop Experience",
                confidence=0.3,
                filters={'expands_to_tags': ['experience:rooftop']},
                matched_text=query,
                reason="fallback:editorial_view"
            )
        else:
            return create_slot(
                type=SlotType.EXPERIENCE,
                canonical="live_music",
                label="Live Music",
                confidence=0.3,
                filters={'expands_to_tags': ['experience:live_music']},
                matched_text=query,
                reason="fallback:editorial_general"
            )
    
    def _create_cooccurrence_fallback_slot(self, query: str) -> Optional[Slot]:
        """Создает fallback слот на основе co-occurrence."""
        query_lower = query.lower()
        
        # Анализируем контекст для определения подходящего слота
        if any(word in query_lower for word in ['chill', 'relax', 'calm', 'quiet']):
            return create_slot(
                type=SlotType.VIBE,
                canonical="chill",
                label="Chill Vibe",
                confidence=0.3,
                filters={'expands_to_tags': ['vibe:chill']},
                matched_text=query,
                reason="fallback:co-occurrence_chill"
            )
        elif any(word in query_lower for word in ['romantic', 'date', 'couple', 'intimate']):
            return create_slot(
                type=SlotType.VIBE,
                canonical="romantic",
                label="Romantic Vibe",
                confidence=0.3,
                filters={'expands_to_tags': ['vibe:romantic']},
                matched_text=query,
                reason="fallback:co-occurrence_romantic"
            )
        elif any(word in query_lower for word in ['art', 'gallery', 'museum', 'culture']):
            return create_slot(
                type=SlotType.EXPERIENCE,
                canonical="gallery",
                label="Gallery Experience",
                confidence=0.3,
                filters={'expands_to_tags': ['experience:gallery']},
                matched_text=query,
                reason="fallback:co-occurrence_art"
            )
        elif any(word in query_lower for word in ['date', 'dating', 'romantic', 'anniversary', 'proposal']):
            return create_slot(
                type=SlotType.VIBE,
                canonical="romantic",
                label="Romantic Vibe",
                confidence=0.3,
                filters={'expands_to_tags': ['vibe:romantic', 'scenario:date']},
                matched_text=query,
                reason="fallback:co-occurrence_romantic"
            )
        elif any(word in query_lower for word in ['music', 'live', 'band', 'concert']):
            return create_slot(
                type=SlotType.EXPERIENCE,
                canonical="live_music",
                label="Live Music",
                confidence=0.3,
                filters={'expands_to_tags': ['experience:live_music']},
                matched_text=query,
                reason="fallback:co-occurrence_music"
            )
        
        return None
    
    def _update_metrics(self, slots_count: int, fallback_used: bool, processing_time: float) -> None:
        """Обновляет метрики работы слоттера."""
        self.metrics.total_queries += 1
        
        if slots_count > 0:
            self.metrics.successful_matches += 1
        
        if fallback_used:
            self.metrics.fallback_used += 1
        
        # Обновляем средние значения
        self.metrics.avg_processing_time_ms = (
            (self.metrics.avg_processing_time_ms * (self.metrics.total_queries - 1) + processing_time) 
            / self.metrics.total_queries
        )
        
        self.metrics.avg_slots_per_query = (
            (self.metrics.avg_slots_per_query * (self.metrics.total_queries - 1) + slots_count) 
            / self.metrics.total_queries
        )
    
    def get_metrics(self) -> SlotterMetrics:
        """Возвращает метрики работы слоттера."""
        return self.metrics
    
    def reset_metrics(self) -> None:
        """Сбрасывает метрики."""
        self.metrics = SlotterMetrics()


# Фабрика для создания QueryBuilder
def create_query_builder(config: SlotterConfig = None) -> QueryBuilder:
    """Создает экземпляр QueryBuilder."""
    return QueryBuilder(config)


# Утилиты для работы с QueryBuilder
def build_slots_from_query(query: str, config: SlotterConfig = None) -> SlotterResult:
    """Удобная функция для извлечения слотов из запроса."""
    builder = create_query_builder(config)
    return builder.build_slots(query)


if __name__ == "__main__":
    # Тестирование QueryBuilder
    builder = create_query_builder()
    
    test_queries = [
        "today i wanna chill, eat tom yum and go on the rooftop",
        "gallery, tea, sushi",
        "romantic dinner with wine",
        "thai food in thonglor"
    ]
    
    print("🔍 Тестирование QueryBuilder...")
    print()
    
    for query in test_queries:
        print(f"Запрос: '{query}'")
        result = builder.build_slots(query)
        
        print(f"   - Слотов: {len(result.slots)}")
        print(f"   - Fallback: {'✅' if result.fallback_used else '❌'}")
        print(f"   - Время: {result.processing_time_ms:.2f}ms")
        
        for slot in result.slots:
            print(f"   - {slot.type}:{slot.canonical} (confidence: {slot.confidence:.2f})")
        
        print()
    
    print("🎯 QueryBuilder готов к работе!")
