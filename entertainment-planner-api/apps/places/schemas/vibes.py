#!/usr/bin/env python3
"""Pydantic schemas for vibes ontology and parsing"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class VibeItem(BaseModel):
    """Single vibe/scenario/experience item"""
    id: str
    aliases: List[str] = Field(default_factory=list)
    boost_default: float = Field(default=1.0, ge=0.0, le=2.0)
    diversity_group: str


class ParsingConfig(BaseModel):
    """Configuration for parsing"""
    confidence_thresholds: Dict[str, float] = Field(
        default_factory=lambda: {
            "vague_queries": 0.4,
            "structured_queries": 0.7
        }
    )
    fallback_llm: bool = True
    cache: Dict[str, Any] = Field(
        default_factory=lambda: {
            "ttl_minutes": 15,
            "max_entries": 1000
        }
    )


class RankingConfig(BaseModel):
    """Configuration for ranking"""
    base_weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "search_score": 1.0,
            "vibe_score": 0.6,
            "novelty": 0.4
        }
    )
    proximity: Dict[str, Any] = Field(
        default_factory=lambda: {
            "enabled": True,
            "anchor_bonus": 0.3,
            "user_bonus": 0.2
        }
    )
    diversity: Dict[str, Any] = Field(
        default_factory=lambda: {
            "enabled": True,
            "top_k": 12,
            "similarity_threshold": 0.3
        }
    )


class ProfilesConfig(BaseModel):
    """Configuration for user profiles"""
    session_ttl_hours: int = Field(default=24, ge=1, le=168)
    max_signals: int = Field(default=100, ge=10, le=1000)
    novelty_decay: float = Field(default=0.9, ge=0.0, le=1.0)


class VibesOntology(BaseModel):
    """Complete vibes ontology"""
    vibes: List[VibeItem] = Field(default_factory=list)
    scenarios: List[VibeItem] = Field(default_factory=list)
    experiences: List[VibeItem] = Field(default_factory=list)
    food_drink_modifiers: List[VibeItem] = Field(default_factory=list)
    parsing: ParsingConfig = Field(default_factory=ParsingConfig)
    ranking: RankingConfig = Field(default_factory=RankingConfig)
    profiles: ProfilesConfig = Field(default_factory=ProfilesConfig)

    model_config = ConfigDict(extra='allow')

    def get_all_items(self) -> Dict[str, List[VibeItem]]:
        """Get all items grouped by type"""
        return {
            "vibes": self.vibes,
            "scenarios": self.scenarios,
            "experiences": self.experiences,
            "food_drink_modifiers": self.food_drink_modifiers
        }

    def get_alias_map(self) -> Dict[str, str]:
        """Create mapping from aliases to main IDs"""
        alias_map = {}
        for item_list in self.get_all_items().values():
            for item in item_list:
                alias_map[item.id] = item.id  # self-reference
                for alias in item.aliases:
                    alias_map[alias.lower()] = item.id
        return alias_map

    def get_boost_map(self) -> Dict[str, float]:
        """Create mapping from IDs to boost values"""
        boost_map = {}
        for item_list in self.get_all_items().values():
            for item in item_list:
                boost_map[item.id] = item.boost_default
        return boost_map


class ParseRequest(BaseModel):
    """Request for parsing user query"""
    query: str = Field(..., min_length=1, max_length=500)
    area: Optional[str] = Field(None, max_length=100)
    user_lat: Optional[float] = Field(None, ge=-90, le=90)
    user_lng: Optional[float] = Field(None, ge=-180, le=180)


class ParseResult(BaseModel):
    """Result of parsing user query"""
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    vibes: List[str] = Field(default_factory=list)
    scenarios: List[str] = Field(default_factory=list)
    experiences: List[str] = Field(default_factory=list)
    filters: Dict[str, Any] = Field(default_factory=dict)
    novelty_preference: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    used_llm: bool = False
    processing_time_ms: float = 0.0
    cache_hit: bool = False
    # Debug information
    debug: Dict[str, Any] = Field(default_factory=dict)


class ComposeRequest(BaseModel):
    """Request for composing search results"""
    parse_result: ParseResult
    area: Optional[str] = Field(None, max_length=100)
    user_lat: Optional[float] = Field(None, ge=-90, le=90)
    user_lng: Optional[float] = Field(None, ge=-180, le=180)
    session_id: Optional[str] = Field(None, max_length=100)
    # Режим выдачи: по умолчанию "light"
    mode: Optional[str] = Field("light", description="light | vibe | surprise")
    # Свободный текст запроса (для slotting)
    query: Optional[str] = Field(None, max_length=200)
    # Тайм-слот (morning|daytime|evening|late_night) — на будущее для open-now boost
    time_slot: Optional[str] = Field(None, description="morning | daytime | evening | late_night")


class PlaceCard(BaseModel):
    """Place card for frontend"""
    id: int
    name: str
    summary: str
    tags_csv: str
    category: str
    lat: float
    lng: float
    address: Optional[str] = None
    picture_url: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    price_level: Optional[int] = None
    rating: Optional[float] = None
    distance_m: Optional[int] = None
    walk_time_min: Optional[int] = None
    search_score: float = 0.0
    vibe_score: float = 0.0
    novelty_score: float = 0.0
    # lightweight UX explainers
    badges: List[str] = Field(default_factory=list)
    # signals for High Experience filtering
    signals: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    why: Optional[str] = None


class Rail(BaseModel):
    """Single rail of results"""
    step: str
    label: str
    items: List[PlaceCard] = Field(default_factory=list)
    origin: Optional[str] = Field(default=None, description="query|complement|signals")
    reason: Optional[str] = Field(default=None, description="short explanation for why this rail was suggested")


class ComposeResponse(BaseModel):
    """Response with composed rails"""
    rails: List[Rail] = Field(default_factory=list)
    processing_time_ms: float = 0.0
    cache_hit: bool = False


class FeedbackRequest(BaseModel):
    """User feedback signal"""
    session_id: str = Field(..., min_length=1, max_length=100)
    place_id: int
    action: str = Field(..., pattern="^(like|unlike|open|add_to_route|dwell)$")
    dwell_ms: Optional[int] = Field(None, ge=0)
    step: Optional[str] = None


class SessionProfile(BaseModel):
    """User session profile"""
    session_id: str
    vibe_vector: Dict[str, float] = Field(default_factory=dict)
    novelty_preference: float = Field(default=0.0, ge=0.0, le=1.0)
    last_areas: List[str] = Field(default_factory=list)
    signals: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: float = Field(default_factory=lambda: __import__('time').time())
    updated_at: float = Field(default_factory=lambda: __import__('time').time())

    def add_signal(self, place_id: int, action: str, dwell_ms: Optional[int] = None, step: Optional[str] = None):
        """Add user signal"""
        signal = {
            "place_id": place_id,
            "action": action,
            "dwell_ms": dwell_ms,
            "step": step,
            "timestamp": __import__('time').time()
        }
        self.signals.append(signal)
        self.updated_at = __import__('time').time()
        
        # Keep only last N signals
        max_signals = 100  # TODO: get from config
        if len(self.signals) > max_signals:
            self.signals = self.signals[-max_signals:]

    def update_vibe_vector(self, place_tags: List[str], action: str, boost: float = 1.0):
        """Update vibe vector based on place tags and action"""
        if action not in ["like", "add_to_route"]:
            return
            
        # Simple implementation - can be enhanced
        for tag in place_tags:
            tag = tag.strip().lower()
            if tag not in self.vibe_vector:
                self.vibe_vector[tag] = 0.0
            self.vibe_vector[tag] += 0.1 * boost
        
        # Normalize
        total = sum(self.vibe_vector.values())
        if total > 0:
            self.vibe_vector = {k: v/total for k, v in self.vibe_vector.items()}
