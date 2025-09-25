"""
Схемы для слоттера - Slot dataclass и связанные типы.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from enum import Enum


class SlotType(str, Enum):
    """Типы слотов."""
    VIBE = "vibe"
    EXPERIENCE = "experience"
    DRINK = "drink"
    CUISINE = "cuisine"
    DISH = "dish"
    AREA = "area"


@dataclass
class Slot:
    """Слот - извлеченный интент из запроса."""
    type: SlotType
    canonical: str
    label: str
    confidence: float
    filters: Dict[str, Any]
    matched_text: str
    reason: str
    context: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Валидация после инициализации."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")
        
        if not self.canonical:
            raise ValueError("Canonical cannot be empty")
        
        if not self.label:
            raise ValueError("Label cannot be empty")


@dataclass
class SlotMatch:
    """Результат матчинга слота."""
    slot: Slot
    matched_synonym: str
    match_type: str  # "exact", "phrase", "multiword", "unigram", "fuzzy"
    confidence: float
    position: int  # позиция в запросе


@dataclass
class SlotterResult:
    """Результат работы слоттера."""
    slots: List[Slot]
    fallback_used: bool
    fallback_reason: Optional[str]
    processing_time_ms: float
    debug_info: Dict[str, Any]


@dataclass
class SlotterConfig:
    """Конфигурация слоттера."""
    min_confidence: float = 0.3
    max_slots: int = 3
    enable_fuzzy: bool = False
    fuzzy_threshold: float = 0.7
    enable_fallback: bool = True
    fallback_strategies: List[str] = None
    
    def __post_init__(self):
        if self.fallback_strategies is None:
            self.fallback_strategies = ["signals:editorial", "co-occurrence"]


@dataclass
class QueryToken:
    """Токен из запроса."""
    text: str
    position: int
    length: int
    is_phrase: bool = False
    is_multiword: bool = False
    is_unigram: bool = True


@dataclass
class SynonymEntry:
    """Запись из словаря синонимов."""
    type: SlotType
    canonical: str
    synonyms: List[str]
    expands_to_tags: List[str]
    denylist: Optional[List[str]] = None
    
    def is_denied(self, text: str) -> bool:
        """Проверяет, запрещен ли текст."""
        if not self.denylist:
            return False
        
        text_lower = text.lower()
        for denied in self.denylist:
            if denied.lower() in text_lower:
                return True
        return False


@dataclass
class SlotterMetrics:
    """Метрики работы слоттера."""
    total_queries: int = 0
    successful_matches: int = 0
    fallback_used: int = 0
    avg_processing_time_ms: float = 0.0
    avg_slots_per_query: float = 0.0
    slot_type_distribution: Dict[str, int] = None
    match_type_distribution: Dict[str, int] = None
    
    def __post_init__(self):
        if self.slot_type_distribution is None:
            self.slot_type_distribution = {}
        if self.match_type_distribution is None:
            self.match_type_distribution = {}


# Утилиты для работы со слотами
def create_slot(
    type: SlotType,
    canonical: str,
    label: str,
    confidence: float,
    filters: Dict[str, Any],
    matched_text: str,
    reason: str,
    context: Optional[Dict[str, Any]] = None
) -> Slot:
    """Создает слот с валидацией."""
    return Slot(
        type=type,
        canonical=canonical,
        label=label,
        confidence=confidence,
        filters=filters,
        matched_text=matched_text,
        reason=reason,
        context=context or {}
    )


def create_slot_match(
    slot: Slot,
    matched_synonym: str,
    match_type: str,
    confidence: float,
    position: int
) -> SlotMatch:
    """Создает результат матчинга слота."""
    return SlotMatch(
        slot=slot,
        matched_synonym=matched_synonym,
        match_type=match_type,
        confidence=confidence,
        position=position
    )


def create_slotter_result(
    slots: List[Slot],
    fallback_used: bool = False,
    fallback_reason: Optional[str] = None,
    processing_time_ms: float = 0.0,
    debug_info: Optional[Dict[str, Any]] = None
) -> SlotterResult:
    """Создает результат работы слоттера."""
    if debug_info is None:
        debug_info = {}
    
    return SlotterResult(
        slots=slots,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        processing_time_ms=processing_time_ms,
        debug_info=debug_info
    )


def create_query_token(
    text: str,
    position: int,
    length: int,
    is_phrase: bool = False,
    is_multiword: bool = False,
    is_unigram: bool = None
) -> QueryToken:
    """Создает токен запроса."""
    if is_unigram is None:
        is_unigram = not (is_phrase or is_multiword)
    
    return QueryToken(
        text=text,
        position=position,
        length=length,
        is_phrase=is_phrase,
        is_multiword=is_multiword,
        is_unigram=is_unigram
    )


def create_synonym_entry(
    type: SlotType,
    canonical: str,
    synonyms: List[str],
    expands_to_tags: List[str],
    denylist: Optional[List[str]] = None
) -> SynonymEntry:
    """Создает запись из словаря синонимов."""
    return SynonymEntry(
        type=type,
        canonical=canonical,
        synonyms=synonyms,
        expands_to_tags=expands_to_tags,
        denylist=denylist
    )
