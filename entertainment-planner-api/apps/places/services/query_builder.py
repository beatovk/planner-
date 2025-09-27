"""
Enhanced query builder with synonyms support
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
    """Enhanced query builder with synonyms support"""
    
    def __init__(self, config: SlotterConfig = None):
        self.config = config or SlotterConfig()
        self.synonyms: Dict[str, SynonymEntry] = {}
        self.metrics = SlotterMetrics()
        self._load_synonyms()
    
    def _load_synonyms(self) -> None:
        """Load synonyms from config/synonyms.yml"""
        try:
            config_path = Path("config/synonyms.yml")
            if not config_path.exists():
                logger.warning("synonyms.yml not found, using empty synonyms")
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
                    
                    # Index by synonyms
                    for synonym in entry.synonyms:
                        self.synonyms[synonym.lower()] = entry
                    
                    # Index by canonical
                    self.synonyms[entry.canonical.lower()] = entry
                    
                except Exception as e:
                    logger.warning(f"Failed to load slot {slot_data.get('canonical', 'unknown')}: {e}")
            
            logger.info(f"Loaded {len(self.synonyms)} synonym entries")
            
        except Exception as e:
            logger.error(f"Failed to load synonyms: {e}")
    
    def build_slots(self, query: str) -> SlotterResult:
        """Extract slots from query"""
        start_time = time.time()
        
        try:
            logger.debug(f"Building slots for query: '{query}'")
            
            # Tokenize query
            tokens = self._tokenize_query(query)
            logger.debug(f"Tokenized query into {len(tokens)} tokens: {[t.text for t in tokens]}")
            
            # Extract slots
            slot_matches = self._extract_slots(tokens)
            logger.debug(f"Extracted {len(slot_matches)} slot matches")
            
            # Sort by confidence and position
            slot_matches.sort(key=lambda x: (-x.confidence, x.position))
            
            # Limit number of slots
            slot_matches = slot_matches[:self.config.max_slots]
            logger.debug(f"Limited to {len(slot_matches)} slots after max_slots filter")
            
            # Create slots
            slots = []
            for match in slot_matches:
                slot = self._create_slot_from_match(match)
                slots.append(slot)
                logger.debug(f"Created slot: {slot.type}:{slot.canonical} (confidence: {slot.confidence:.2f})")

            # Context: if there's a dish slot, mark all as has_dish=True
            try:
                has_dish = any(s.type == SlotType.DISH for s in slots)
                if has_dish:
                    for slot in slots:
                        slot.context['has_dish'] = True
            except Exception as e:
                logger.warning(f"Failed to set dish context: {e}")

            processing_time = (time.time() - start_time) * 1000
            
            # Update metrics
            self._update_metrics(len(slots) > 0, False, processing_time, len(slots))
            
            return create_slotter_result(
                slots=slots,
                fallback_used=False,
                fallback_reason=None,
                processing_time_ms=processing_time,
                debug_info={
                    "query": query,
                    "tokens": [t.text for t in tokens],
                    "synonyms_checked": len(self.synonyms)
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to build slots: {e}")
            return create_slotter_result(
                slots=[],
                fallback_used=True,
                fallback_reason=f"Error: {e}",
                processing_time_ms=(time.time() - start_time) * 1000,
                debug_info={"error": str(e)}
            )
    
    def _tokenize_query(self, query: str) -> List[QueryToken]:
        """Tokenize query into tokens"""
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
    
    def _extract_slots(self, tokens: List[QueryToken]) -> List[SlotMatch]:
        """Extract slots from tokens"""
        slot_matches = []
        used_tokens = set()
        
        # 1. Exact matches
        for token in tokens:
            if token.text in used_tokens:
                continue
                
            match = self._match_exact_token(token)
            if match:
                slot_matches.append(match)
                used_tokens.add(token.text)
        
        # 2. Phrase matches (2-3 tokens)
        for i, token in enumerate(tokens):
            if token.text in used_tokens:
                continue
                
            for length in [2, 3]:
                if i + length <= len(tokens):
                    phrase_tokens = tokens[i:i+length]
                    phrase_text = " ".join([t.text for t in phrase_tokens])
                    
                    if phrase_text in used_tokens:
                        continue
                    
                    match = self._match_phrase(phrase_text, phrase_tokens)
                    if match:
                        slot_matches.append(match)
                        used_tokens.add(phrase_text)
                        # Mark used tokens
                        for t in phrase_tokens:
                            used_tokens.add(t.text)
                        break
        
        return slot_matches
    
    def _match_exact_token(self, token: QueryToken) -> Optional[SlotMatch]:
        """Match exact token"""
        if token.text in self.synonyms:
            entry = self.synonyms[token.text]
            return create_slot_match(
                slot=create_slot(
                    type=entry.type,
                    canonical=entry.canonical,
                    label=entry.canonical.replace("_", " ").title(),
                    confidence=1.0,
                    filters={"expands_to_tags": entry.expands_to_tags},
                    matched_text=token.text,
                    reason="exact_match"
                ),
                matched_synonym=token.text,
                match_type="exact",
                confidence=1.0,
                position=token.position
            )
        return None
    
    def _match_phrase(self, phrase: str, tokens: List[QueryToken]) -> Optional[SlotMatch]:
        """Match phrase"""
        if phrase in self.synonyms:
            entry = self.synonyms[phrase]
            return create_slot_match(
                slot=create_slot(
                    type=entry.type,
                    canonical=entry.canonical,
                    label=entry.canonical.replace("_", " ").title(),
                    confidence=1.0,
                    filters={"expands_to_tags": entry.expands_to_tags},
                    matched_text=phrase,
                    reason="phrase_match"
                ),
                matched_synonym=phrase,
                match_type="phrase",
                confidence=1.0,
                position=tokens[0].position
            )
        return None
    
    def _create_slot_from_match(self, match: SlotMatch) -> Slot:
        """Create slot from match"""
        return match.slot
    
    def _update_metrics(self, success: bool, fallback_used: bool, processing_time: float, slots_count: int):
        """Update metrics"""
        self.metrics.total_queries += 1
        if success:
            self.metrics.successful_matches += 1
        if fallback_used:
            self.metrics.fallback_used += 1
        
        # Update averages
        total = self.metrics.total_queries
        self.metrics.avg_processing_time_ms = (
            (self.metrics.avg_processing_time_ms * (total - 1) + processing_time) / total
        )
        self.metrics.avg_slots_per_query = (
            (self.metrics.avg_slots_per_query * (total - 1) + slots_count) / total
        )

def create_query_builder(config: SlotterConfig = None) -> QueryBuilder:
    """Create query builder instance"""
    return QueryBuilder(config)