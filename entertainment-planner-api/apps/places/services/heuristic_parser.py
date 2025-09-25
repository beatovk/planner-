#!/usr/bin/env python3
"""Heuristic parser for user queries with dynamic confidence threshold"""

import re
import time
import logging
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import yaml
from pathlib import Path
from difflib import SequenceMatcher

from apps.places.schemas.vibes import VibesOntology, ParseRequest, ParseResult

logger = logging.getLogger(__name__)


@dataclass
class ParsedStep:
    """Single parsed step from user query"""
    intent: str  # restaurant, activity, drinks, etc.
    query: str   # original query part
    vibes: List[str]
    scenarios: List[str]
    experiences: List[str]
    confidence: float


class HeuristicParser:
    """Heuristic parser with dynamic confidence threshold"""
    
    def __init__(self, ontology: VibesOntology):
        self.ontology = ontology
        self.alias_map = ontology.get_alias_map()
        self.boost_map = ontology.get_boost_map()
        
        # Common misspellings and corrections (только реальные опечатки)
        self.corrections = {
            'coffe': 'coffee',
            'cofee': 'coffee',
            'cofeee': 'coffee',
            'cafe': 'coffee',
            'café': 'coffee',
            'resturant': 'restaurant',
            'restaraunt': 'restaurant',
            'roof top': 'rooftop',
            'roof-top': 'rooftop',
            'tom yum': 'tom yum',
            'tomyum': 'tom yum',
            'tom-yum': 'tom yum',
            'hip hop': 'hip hop',
            'hiphop': 'hip hop',
            'hip-hop': 'hip hop'
        }
        
        # Intent keywords with fuzzy matching
        self.intent_keywords = {
            'restaurant': ['eat', 'food', 'dinner', 'lunch', 'breakfast', 'restaurant', 'cafe', 'coffee', 'tea', 'tom yum', 'thai', 'japanese', 'italian', 'chinese', 'korean', 'mexican', 'french', 'indian', 'pizza', 'burger', 'sushi', 'ramen', 'pasta', 'steak', 'seafood', 'vegetarian', 'vegan', 'halal', 'kosher'],
            'drinks': ['drink', 'bar', 'pub', 'club', 'nightlife', 'cocktail', 'wine', 'beer', 'whiskey', 'sake', 'rooftop', 'terrace', 'party', 'dance', 'music', 'live', 'jazz', 'blues', 'rock', 'electronic', 'dj', 'karaoke'],
            'activity': ['do', 'see', 'visit', 'explore', 'walk', 'stroll', 'park', 'museum', 'gallery', 'temple', 'palace', 'market', 'shopping', 'tour', 'guide', 'experience', 'adventure', 'fun', 'entertainment'],
            'wellness': ['spa', 'massage', 'wellness', 'relax', 'therapy', 'beauty', 'salon', 'facial', 'manicure', 'pedicure', 'sauna', 'steam', 'jacuzzi', 'hot spring', 'onsen', 'meditation', 'yoga', 'pilates', 'fitness', 'gym'],
            'culture': ['culture', 'art', 'museum', 'gallery', 'exhibition', 'theater', 'theatre', 'show', 'performance', 'concert', 'opera', 'ballet', 'dance', 'traditional', 'heritage', 'history', 'temple', 'palace', 'monument', 'landmark'],
            'shopping': ['shop', 'shopping', 'mall', 'market', 'boutique', 'store', 'buy', 'purchase', 'fashion', 'clothes', 'souvenir', 'gift', 'bargain', 'deal', 'sale', 'luxury', 'designer', 'brand']
        }
        
        # Compile regex patterns for better performance
        self._compile_patterns()
        
    def _compile_patterns(self):
        """Compile regex patterns for parsing"""
        # Intent patterns (порядок важен - более специфичные первыми)
        self.intent_patterns = {
            'drinks': re.compile(r'\b(drink|bar|pub|club|nightlife|cocktail|wine|beer|whiskey|sake|rooftop|terrace|party|dance|music|live|jazz|blues|rock|electronic|dj|karaoke)\b', re.IGNORECASE),
            'restaurant': re.compile(r'\b(eat|food|dinner|lunch|breakfast|restaurant|cafe|coffee|tea|tom yum|thai|japanese|italian|chinese|korean|mexican|french|indian|pizza|burger|sushi|ramen|pasta|steak|seafood|vegetarian|vegan|halal|kosher)\b', re.IGNORECASE),
            'activity': re.compile(r'\b(do|see|visit|explore|walk|stroll|park|museum|gallery|temple|palace|market|shopping|spa|massage|yoga|gym|pool|beach|island|tour|guide|experience|adventure|fun|entertainment)\b', re.IGNORECASE),
            'wellness': re.compile(r'\b(spa|massage|wellness|relax|therapy|beauty|salon|facial|manicure|pedicure|sauna|steam|jacuzzi|hot spring|onsen|meditation|yoga|pilates|fitness|gym)\b', re.IGNORECASE),
            'culture': re.compile(r'\b(culture|art|museum|gallery|exhibition|theater|theatre|show|performance|concert|opera|ballet|dance|traditional|heritage|history|temple|palace|monument|landmark)\b', re.IGNORECASE),
            'shopping': re.compile(r'\b(shop|shopping|mall|market|boutique|store|buy|purchase|fashion|clothes|souvenir|gift|bargain|deal|sale|luxury|designer|brand)\b', re.IGNORECASE)
        }
        
        # Vague query patterns
        self.vague_patterns = [
            re.compile(r'\b(something|anything|what|where|how|interesting|fun|cool|nice|good|great|amazing|wonderful|awesome|fantastic|surprise|surprise me|wow|wow me)\b', re.IGNORECASE),
            re.compile(r'\b(new|different|unique|special|unusual|unexpected|hidden|secret|offbeat|quirky|weird|strange|bizarre|exotic|local|authentic)\b', re.IGNORECASE),
            re.compile(r'\b(romantic|date|couple|love|intimate|cozy|chill|relax|peaceful|quiet|calm|serene|tranquil)\b', re.IGNORECASE)
        ]
        
        # Structured query patterns
        self.structured_patterns = [
            re.compile(r'\b(tom yum|spa|rooftop|thonglor|sukhumvit|silom|chinatown|khaosan|chatuchak|terminal21|iconsiam|mbk|central|paragon|emquartier|siam|asok|nana|phrom phong|thong lo|ekkamai|on nut|bangna|udom suk|bang chak|punnawithi|bang wa|bang khae|bang phai|bang yai|bang bua thong|bang kruai|bang sue|chatuchak|lat phrao|huai khwang|sutthisan|ratchadapisek|rama 9|thailand cultural center|phra khanong|on nut|bang na|udom suk|bang chak|punnawithi|bang wa|bang khae|bang phai|bang yai|bang bua thong|bang kruai|bang sue|chatuchak|lat phrao|huai khwang|sutthisan|ratchadapisek|rama 9|thailand cultural center|phra khanong)\b', re.IGNORECASE)
        ]
        
    def parse(self, request: ParseRequest) -> ParseResult:
        """Parse user query with dynamic confidence threshold"""
        start_time = time.time()
        
        # Determine query type and confidence threshold
        query_type = self._classify_query_type(request.query)
        confidence_threshold = self._get_confidence_threshold(query_type)
        
        # Parse query into steps
        steps = self._parse_steps(request.query)
        
        # Extract vibes, scenarios, experiences
        vibes = self._extract_vibes(request.query)
        scenarios = self._extract_scenarios(request.query)
        experiences = self._extract_experiences(request.query)
        
        # Calculate overall confidence
        confidence = self._calculate_confidence(steps, vibes, scenarios, experiences)
        
        # Extract filters
        filters = self._extract_filters(request)
        
        # Calculate novelty preference
        novelty_preference = self._calculate_novelty_preference(request.query, vibes)
        
        processing_time = (time.time() - start_time) * 1000
        
        # Debug information
        debug_info = {
            "query_type": query_type,
            "confidence_threshold": confidence_threshold,
            "applied_corrections": [],
            "fuzzy_matches": [],
            "tokens_used": 0,  # Heuristic parser doesn't use tokens
            "aliases_found": []
        }
        
        return ParseResult(
            steps=[step.__dict__ for step in steps],
            vibes=vibes,
            scenarios=scenarios,
            experiences=experiences,
            filters=filters,
            novelty_preference=novelty_preference,
            confidence=confidence,
            used_llm=False,  # Heuristic parser doesn't use LLM
            processing_time_ms=processing_time,
            debug=debug_info
        )
    
    def _classify_query_type(self, query: str) -> str:
        """Classify query as vague or structured"""
        query_lower = query.lower()
        
        # Check for vague patterns
        for pattern in self.vague_patterns:
            if pattern.search(query_lower):
                return "vague"
        
        # Check for structured patterns
        for pattern in self.structured_patterns:
            if pattern.search(query_lower):
                return "structured"
        
        # Default to structured if no patterns match
        return "structured"
    
    def _get_confidence_threshold(self, query_type: str) -> float:
        """Get confidence threshold based on query type"""
        return self.ontology.parsing.confidence_thresholds.get(
            f"{query_type}_queries", 0.5
        )
    
    def _parse_steps(self, query: str) -> List[ParsedStep]:
        """Parse query into steps (intents) using improved AI parser"""
        # Always use heuristic parsing for now (AI parser not available)
        return self._parse_steps_heuristic(query)
    
    def _parse_steps_heuristic(self, query: str) -> List[ParsedStep]:
        """Original heuristic parsing as fallback"""
        steps = []
        
        # Split by common separators
        parts = re.split(r'[,;]|\bthen\b|\bafter\b|\bnext\b|\band then\b', query, flags=re.IGNORECASE)
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            # Determine intent
            intent = self._determine_intent(part)
            
            # Extract vibes, scenarios, experiences for this step
            step_vibes = self._extract_vibes(part)
            step_scenarios = self._extract_scenarios(part)
            step_experiences = self._extract_experiences(part)
            
            # Calculate confidence for this step
            step_confidence = self._calculate_step_confidence(part, intent, step_vibes, step_scenarios, step_experiences)
            
            steps.append(ParsedStep(
                intent=intent,
                query=part,
                vibes=step_vibes,
                scenarios=step_scenarios,
                experiences=step_experiences,
                confidence=step_confidence
            ))
        
        # If no steps found, create a default one
        if not steps:
            steps.append(ParsedStep(
                intent="general",
                query=query,
                vibes=[],
                scenarios=[],
                experiences=[],
                confidence=0.3
            ))
        
        return steps
    
    def _determine_intent(self, query_part: str) -> str:
        """Determine intent for a query part"""
        query_lower = query_part.lower()
        
        # Apply corrections first (только точные совпадения слов)
        corrected_query = query_lower
        for typo, correction in self.corrections.items():
            # Используем word boundaries для точных совпадений
            import re
            corrected_query = re.sub(r'\b' + re.escape(typo) + r'\b', correction, corrected_query)
        
        # Check each intent pattern
        for intent, pattern in self.intent_patterns.items():
            if pattern.search(corrected_query):
                logger.debug(f"Found intent '{intent}' for query '{query_part}' (corrected: '{corrected_query}')")
                return intent
        
        # Default to general
        logger.debug(f"No intent found for query '{query_part}' (corrected: '{corrected_query}')")
        return "general"
    
    def _extract_vibes(self, query: str) -> List[str]:
        """Extract vibes from query with fuzzy matching"""
        vibes = []
        query_lower = query.lower()
        
        # Apply corrections first
        corrected_query = query_lower
        for typo, correction in self.corrections.items():
            corrected_query = corrected_query.replace(typo, correction)
        
        for vibe in self.ontology.vibes:
            # Check main ID
            if vibe.id in corrected_query:
                vibes.append(vibe.id)
                continue
            
            # Check aliases
            for alias in vibe.aliases:
                if alias.lower() in corrected_query:
                    vibes.append(vibe.id)
                    break
            
            # Fuzzy matching for typos (similarity > 0.8)
            for word in corrected_query.split():
                if len(word) > 3:  # Only for words longer than 3 chars
                    similarity = SequenceMatcher(None, vibe.id, word).ratio()
                    if similarity > 0.8:
                        vibes.append(vibe.id)
                        break
        
        return list(set(vibes))  # Remove duplicates
    
    def _extract_scenarios(self, query: str) -> List[str]:
        """Extract scenarios from query"""
        scenarios = []
        query_lower = query.lower()
        
        for scenario in self.ontology.scenarios:
            # Check main ID
            if scenario.id in query_lower:
                scenarios.append(scenario.id)
                continue
            
            # Check aliases
            for alias in scenario.aliases:
                if alias.lower() in query_lower:
                    scenarios.append(scenario.id)
                    break
        
        return list(set(scenarios))
    
    def _extract_experiences(self, query: str) -> List[str]:
        """Extract experiences from query"""
        experiences = []
        query_lower = query.lower()
        
        for experience in self.ontology.experiences:
            # Check main ID
            if experience.id in query_lower:
                experiences.append(experience.id)
                continue
            
            # Check aliases
            for alias in experience.aliases:
                if alias.lower() in query_lower:
                    experiences.append(experience.id)
                    break
        
        return list(set(experiences))
    
    def _extract_filters(self, request: ParseRequest) -> Dict[str, Any]:
        """Extract filters from request"""
        filters = {}
        
        if request.area:
            filters["area"] = request.area
        
        if request.user_lat and request.user_lng:
            filters["user_lat"] = request.user_lat
            filters["user_lng"] = request.user_lng
        
        return filters
    
    def _calculate_novelty_preference(self, query: str, vibes: List[str]) -> float:
        """Calculate novelty preference from query and vibes"""
        query_lower = query.lower()
        
        # Check for novelty keywords
        novelty_keywords = [
            "new", "different", "unique", "special", "unusual", "unexpected",
            "hidden", "secret", "offbeat", "quirky", "weird", "strange",
            "bizarre", "exotic", "surprise", "wow", "amazing", "wonderful"
        ]
        
        novelty_score = 0.0
        for keyword in novelty_keywords:
            if keyword in query_lower:
                novelty_score += 0.1
        
        # Check for hidden_gem vibe
        if "hidden_gem" in vibes:
            novelty_score += 0.3
        
        # Check for artsy vibe (often novel)
        if "artsy" in vibes:
            novelty_score += 0.2
        
        return min(novelty_score, 1.0)
    
    def _calculate_step_confidence(self, query_part: str, intent: str, vibes: List[str], scenarios: List[str], experiences: List[str]) -> float:
        """Calculate confidence for a single step"""
        confidence = 0.0
        
        # Base confidence from intent detection
        if intent != "general":
            confidence += 0.4
        
        # Boost from vibes
        confidence += len(vibes) * 0.1
        
        # Boost from scenarios
        confidence += len(scenarios) * 0.1
        
        # Boost from experiences
        confidence += len(experiences) * 0.1
        
        # Boost from specific keywords
        if any(word in query_part.lower() for word in ["tom yum", "rooftop", "spa", "massage", "jazz", "wine", "coffee"]):
            confidence += 0.2
        
        return min(confidence, 1.0)
    
    def _calculate_confidence(self, steps: List[ParsedStep], vibes: List[str], scenarios: List[str], experiences: List[str]) -> float:
        """Calculate overall confidence for the parse result"""
        if not steps:
            return 0.0
        
        # Average step confidence
        step_confidence = sum(step.confidence for step in steps) / len(steps)
        
        # Boost from extracted elements
        element_boost = (len(vibes) + len(scenarios) + len(experiences)) * 0.05
        
        return min(step_confidence + element_boost, 1.0)


def load_ontology(config_path: str = "config/vibes.yml") -> VibesOntology:
    """Load vibes ontology from YAML file"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return VibesOntology.model_validate(data)
    except Exception as e:
        logger.error(f"Failed to load ontology from {config_path}: {e}")
        # Return default ontology
        return VibesOntology()


def create_heuristic_parser(config_path: str = "config/vibes.yml") -> HeuristicParser:
    """Create heuristic parser with loaded ontology"""
    ontology = load_ontology(config_path)
    return HeuristicParser(ontology)
