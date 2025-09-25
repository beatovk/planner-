#!/usr/bin/env python3
"""3-stage ranking service for Netflix-style search"""

import time
import math
import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text

from apps.places.models import Place
from apps.places.schemas.vibes import ParseResult, PlaceCard, Rail, ComposeRequest, ComposeResponse, SessionProfile
from apps.places.services.bitset_service import BitsetService
from apps.places.services.search import SearchService

logger = logging.getLogger(__name__)


class RankingService:
    """3-stage ranking service: Base → Proximity → Diversity"""
    
    def __init__(self, bitset_service: BitsetService, search_service: SearchService):
        self.bitset_service = bitset_service
        self.search_service = search_service
        
    def compose_rails(self, request: ComposeRequest, db: Session, profile: Optional[SessionProfile] = None) -> ComposeResponse:
        """Compose search results into rails with 3-stage ranking"""
        start_time = time.time()
        
        # Устанавливаем режим для использования в ранжировании
        self._mode = request.mode or "light"
        
        try:
            rails = []
            
            # Get global scenarios and vibes from parse result
            global_scenarios = request.parse_result.scenarios or []
            global_vibes = request.parse_result.vibes or []
            
            # Process each step from parse result
            for step_data in request.parse_result.steps:
                step = step_data.get('intent', 'general')
                query = step_data.get('query', '')
                step_vibes = step_data.get('vibes', global_vibes)  # Use step vibes or fallback to global
                step_scenarios = step_data.get('scenarios', global_scenarios)  # Use step scenarios or fallback to global
                step_experiences = step_data.get('experiences', [])
                
                logger.info(f"Processing step: {step} with query: {query}")
                
                # Get candidates for this step
                candidates = self._get_candidates(
                    db, step, query, step_vibes, step_scenarios, step_experiences, request
                )
                
                logger.info(f"Candidates for step {step}: {len(candidates) if candidates else 'None'}")
                
                if not candidates or candidates is None:
                    logger.info(f"Skipping step {step} - no candidates")
                    continue
                
                # Stage 1: Base ranking
                ranked_candidates = self._stage1_base_ranking(
                    candidates, step_vibes, step_scenarios, step_experiences, profile
                )
                logger.info(f"After stage 1: {len(ranked_candidates) if ranked_candidates else 'None'} candidates")
                
                # Stage 2: Proximity re-sorting
                ranked_candidates = self._stage2_proximity_sorting(
                    ranked_candidates, request
                )
                logger.info(f"After stage 2: {len(ranked_candidates) if ranked_candidates else 'None'} candidates")
                
                # Stage 3: Diversity (MMR)
                final_candidates = self._stage3_diversity(
                    ranked_candidates, top_k=12
                )
                logger.info(f"After stage 3: {len(final_candidates) if final_candidates else 'None'} candidates")
                
                # Convert to PlaceCard objects
                place_cards = self._convert_to_place_cards(final_candidates, request)
                logger.info(f"Place cards: {len(place_cards) if place_cards else 'None'} cards")
                
                # Create rail
                rail = Rail(
                    step=step,
                    label=self._get_rail_label(step),
                    items=place_cards
                )
                rails.append(rail)
            
            # КРИТИЧНО: Глобальная дедупликация между rails
            rails = self._deduplicate_rails(rails)
            
            processing_time = (time.time() - start_time) * 1000
            
            return ComposeResponse(
                rails=rails,
                processing_time_ms=processing_time,
                cache_hit=False
            )
            
        except Exception as e:
            logger.error(f"Failed to compose rails: {e}")
            raise
    
    def _deduplicate_rails(self, rails: List[Rail]) -> List[Rail]:
        """
        Глобальная дедупликация между rails:
        - Удаляет дубликаты по ID и названию
        - Сохраняет первое вхождение (приоритет по порядку rails)
        """
        seen_ids = set()
        seen_names = set()
        
        deduplicated_rails = []
        
        for rail in rails:
            unique_items = []
            
            for item in rail.items:
                # Проверяем по ID (приоритет)
                if item.id and item.id != 0:
                    if item.id in seen_ids:
                        continue  # Пропускаем дубликат по ID
                    seen_ids.add(item.id)
                else:
                    # Если ID нет, проверяем по названию
                    name_key = item.name.lower().strip()
                    if name_key in seen_names:
                        continue  # Пропускаем дубликат по названию
                    seen_names.add(name_key)
                
                unique_items.append(item)
            
            # Создаем новую rail с уникальными элементами
            if unique_items:  # Только если есть уникальные элементы
                deduplicated_rail = Rail(
                    step=rail.step,
                    label=rail.label,
                    items=unique_items
                )
                deduplicated_rails.append(deduplicated_rail)
        
        logger.info(f"Дедупликация: {len(rails)} rails → {len(deduplicated_rails)} rails")
        return deduplicated_rails
    
    def _get_candidates(self, db: Session, step: str, query: str, vibes: List[str], 
                       scenarios: List[str], experiences: List[str], request: ComposeRequest) -> List[Place]:
        """Get candidate places for a step using FTS5"""
        try:
            # Build effective query from original request and AI parser data
            effective_query = query or request.query or ""
            
            # If still no query, try to build from AI parser step data
            if not effective_query.strip():
                step_data = None
                for step_item in request.parse_result.steps:
                    if step_item.get('intent') == step:
                        step_data = step_item
                        break
                
                if step_data:
                    # Build query from AI parser categories and tags
                    query_parts = []
                    categories = step_data.get('category', [])
                    tags = step_data.get('tags', [])
                    
                    # Use categories and tags to build search query
                    if categories:
                        query_parts.extend(categories)
                    if tags:
                        query_parts.extend(tags)
                    
                    effective_query = " ".join(query_parts)
            
            logger.info(f"Getting candidates for step '{step}' with effective query '{effective_query}'")
            
            # Use injected search service and bind DB per-request
            search_service = self.search_service.bind_db(db)
            
            # Use search service to get candidates
            search_params = {
                'query': effective_query,
                'limit': 40,  # Get more candidates for ranking
                'area': request.area,
                'user_lat': request.user_lat,
                'user_lng': request.user_lng
            }
            
            # Note: SearchService doesn't support category filtering
            # We'll filter by category after getting results
            
            # Use search service to get candidates
            search_results = search_service.search_places(**search_params)
            logger.info(f"Search service returned: {type(search_results)}")
            
            # SearchService returns a list of places, not a dict
            if isinstance(search_results, list):
                candidates = search_results
            elif isinstance(search_results, dict):
                candidates = search_results.get('places', [])
            else:
                candidates = []
            
            logger.info(f"Initial candidates count: {len(candidates)}")
            
            # Apply scenario-based filtering at candidate level
            filtered_candidates = []
            global_scenarios = request.parse_result.scenarios or []
            all_scenarios = scenarios + global_scenarios
            
            for candidate in candidates:
                if all_scenarios and ('date' in all_scenarios or 'first_date' in all_scenarios):
                    # normalize once
                    place_tags_list = [t.strip().lower() for t in (candidate.get('tags_csv') or '').split(',') if t.strip()]
                    place_tags = " ".join(place_tags_list)
                    place_name = (candidate.get('name') or '').lower()
                    place_summary = (candidate.get('summary') or '').lower()
                    
                    # Smart filtering: only exclude clearly non-romantic places
                    # Check for romantic context first - expanded keywords
                    romantic_context = any(keyword in place_tags or keyword in place_name or keyword in place_summary 
                                         for keyword in [
                                             'rooftop', 'view', 'sunset', 'intimate', 'cozy', 'candle', 'wine', 'champagne', 
                                             'fine dining', 'luxury', 'elegant', 'stunning views', 'panoramic', 'skyline',
                                             'candlelit', 'wine tasting', 'champagne brunch', 'sunset dinner', 'moonlit',
                                             'starlit', 'breathtaking', 'magical', 'enchanting', 'dreamy', 'perfect for two',
                                             'intimate dining', 'romantic atmosphere', 'special occasion', 'couples',
                                             'anniversary', 'proposal', 'valentine', 'love', 'passion', 'sweet', 'tender',
                                             'sophisticated', 'upscale', 'quiet', 'peaceful', 'serene'
                                         ])
                    
                    # Only exclude if clearly non-romantic AND no romantic context
                    clearly_non_romantic = any(keyword in place_tags or keyword in place_name or keyword in place_summary 
                                             for keyword in [
                                                 'sports bar', 'sports', 'football', 'soccer', 'gaming', 'arcade', 
                                                 'pool hall', 'billiards', 'brewery', 'beer', 'party', 'loud', 'crowded',
                                                 'fast food', 'buffet', 'family', 'kids', 'playground', 'casual', 'noisy',
                                                 'pub', 'club', 'nightclub', 'energetic', 'tawandang', 'german',
                                                 'sports tv', 'gaming zone', 'arcade games', 'pool table', 'billiards table',
                                                 'fast casual', 'buffet style', 'family style', 'kids menu', 'playground area',
                                                 'casual vibe', 'noisy atmosphere', 'bar food', 'pub style', 'club style',
                                                 'nightclub style', 'party atmosphere', 'loud music', 'crowded bar'
                                             ])
                    
                    if clearly_non_romantic and not romantic_context:
                        continue  # Skip this place
                
                filtered_candidates.append(candidate)
            
            logger.info(f"Final candidates count: {len(filtered_candidates)} for step '{step}' with query '{query}'")
            return filtered_candidates
            
        except Exception as e:
            logger.error(f"Failed to get candidates for step {step}: {e}")
            return []
    
    def _stage1_base_ranking(self, candidates: List[Dict[str, Any]], vibes: List[str], 
                            scenarios: List[str], experiences: List[str], 
                            profile: Optional[SessionProfile]) -> List[Tuple[Dict[str, Any], Dict[str, float]]]:
        """Stage 1: Base ranking with search_score + vibe_score + novelty"""
        # режим берём из self._mode, который выставляется в compose_rails()
        mode = getattr(self, "_mode", "light")
        
        if candidates is None:
            logger.warning("_stage1_base_ranking received None candidates")
            return []
        
        ranked = []
        
        for place in candidates:
            scores = {}
            
            # Search score (from FTS5) - normalize to 0-1
            search_score = place.get('search_score', 0.5)  # Default if not set
            scores['search_score'] = min(search_score / 1000.0, 1.0)  # Normalize from 0-1000 to 0-1
            
            # Vibe score using bitset or tags_csv
            vibe_score = 0.0
            tag_bitset = place.get('tag_bitset')
            if tag_bitset and profile and profile.vibe_vector:
                vibe_score = self.bitset_service.calculate_vibe_score_with_weights(
                    tag_bitset, profile.vibe_vector
                )
            elif tag_bitset and vibes:
                # Fallback to simple vibe matching
                place_vibes = self.bitset_service.bitset_to_tags(tag_bitset)
                common_vibes = set(place_vibes) & set(vibes)
                if vibes:
                    vibe_score = len(common_vibes) / len(vibes)
            elif vibes:
                # Fallback to tags_csv matching (case-insensitive, без ':'-условия)
                place_tags = [t.strip().lower() for t in (place.get('tags_csv') or '').split(',') if t.strip()]
                place_vibes = place_tags
                common_vibes = set(place_vibes) & set([v.lower() for v in vibes])
                if vibes:
                    vibe_score = len(common_vibes) / len(vibes)
            
            # Scenario-based scoring
            scenario_bonus = 0.0
            if scenarios:
                if tag_bitset:
                    place_tags = self.bitset_service.bitset_to_tags(tag_bitset)
                else:
                    place_tags = [t.strip().lower() for t in (place.get('tags_csv') or '').split(',') if t.strip()]
                place_name = (place.get('name') or '').lower()
                place_summary = (place.get('summary') or '').lower()
                
                # Debug logging for specific places
                debug_places = ['onyx', 'viu', 'tawandang', 'number 1 gallery']
                is_debug_place = any(debug_name in place_name for debug_name in debug_places)
                
                for scenario in scenarios:
                    if scenario == 'date' or scenario == 'first_date':
                        # Enhanced romantic context analysis
                        romantic_keywords = [
                            'romantic', 'intimate', 'cozy', 'candle', 'sunset', 'fine dining', 'luxury', 'elegant', 
                            'sophisticated', 'upscale', 'quiet', 'peaceful', 'serene', 'stunning views', 'panoramic', 
                            'skyline', 'candlelit', 'wine tasting', 'champagne brunch', 'sunset dinner', 'moonlit',
                            'starlit', 'breathtaking', 'magical', 'enchanting', 'dreamy', 'perfect for two',
                            'intimate dining', 'romantic atmosphere', 'special occasion', 'couples', 'anniversary',
                            'proposal', 'valentine', 'love', 'passion', 'sweet', 'tender'
                        ]
                        romantic_matches = [keyword for keyword in romantic_keywords if keyword in place_tags or keyword in place_name or keyword in place_summary]
                        
                        # Context-aware scoring
                        if romantic_matches:
                            # Higher bonus for multiple romantic keywords
                            bonus = 0.3 + (len(romantic_matches) - 1) * 0.1
                            scenario_bonus += min(bonus, 0.6)  # Cap at 0.6
                            if is_debug_place:
                                print(f"DEBUG {place_name}: Romantic bonus +{min(bonus, 0.6):.2f} for keywords: {romantic_matches}")
                        
                        # Special bonus for rooftop + view combination
                        if 'rooftop' in place_tags and 'view' in place_summary:
                            scenario_bonus += 0.2
                            if is_debug_place:
                                print(f"DEBUG {place_name}: Rooftop+view bonus +0.2")
                        
                        # Special bonus for wine + romantic context
                        if 'wine' in place_tags and any(word in place_summary for word in ['romantic', 'intimate', 'cozy', 'candle']):
                            scenario_bonus += 0.15
                            if is_debug_place:
                                print(f"DEBUG {place_name}: Wine+romantic context bonus +0.15")
                        
                        # Penalize non-romantic places (but less aggressively)
                        non_romantic_keywords = [
                            'brewery', 'beer', 'party', 'loud', 'crowded', 'sports', 'fast food', 'buffet', 
                            'family', 'kids', 'german', 'energetic', 'nightlife', 'sports bar', 'gaming', 
                            'arcade', 'pool hall', 'billiards', 'tawandang'
                        ]
                        non_romantic_matches = [keyword for keyword in non_romantic_keywords if keyword in place_tags or keyword in place_name or keyword in place_summary]
                        
                        if non_romantic_matches:
                            # Check if there's romantic context to mitigate penalty
                            has_romantic_context = any(keyword in place_tags or keyword in place_name or keyword in place_summary 
                                                     for keyword in ['rooftop', 'view', 'sunset', 'intimate', 'cozy', 'wine', 'champagne'])
                            
                            if has_romantic_context:
                                # Reduced penalty if there's romantic context
                                penalty = -0.1
                                if is_debug_place:
                                    print(f"DEBUG {place_name}: Non-romantic penalty reduced to {penalty} due to romantic context")
                            else:
                                # Full penalty if no romantic context
                                penalty = -0.3 if len(non_romantic_matches) > 1 else -0.2
                                if is_debug_place:
                                    print(f"DEBUG {place_name}: Non-romantic penalty {penalty} for keywords: {non_romantic_matches}")
                            
                            scenario_bonus += penalty
                        
                        if is_debug_place:
                            print(f"DEBUG {place_name}: Final scenario_bonus = {scenario_bonus}")
                            print(f"DEBUG {place_name}: place_tags = {place_tags}")
                            print(f"DEBUG {place_name}: place_name = {place_name}")
                            print(f"DEBUG {place_name}: place_summary = {place_summary[:100]}...")
                    
                    elif scenario == 'business':
                        # Business-friendly places
                        business_keywords = ['professional', 'quiet', 'formal', 'meeting', 'conference', 'upscale', 'sophisticated']
                        if any(keyword in place_tags or keyword in place_name or keyword in place_summary for keyword in business_keywords):
                            scenario_bonus += 0.3
                    
                    elif scenario == 'family':
                        # Family-friendly places
                        family_keywords = ['family', 'kids', 'friendly', 'casual', 'outdoor', 'fun', 'playground']
                        if any(keyword in place_tags or keyword in place_name or keyword in place_summary for keyword in family_keywords):
                            scenario_bonus += 0.3
            
            # Apply scenario bonus to vibe_score
            final_vibe_score = max(0.0, min(1.0, vibe_score + scenario_bonus))
            
            # For romantic date scenarios, apply additional filtering
            if scenarios and ('date' in scenarios or 'first_date' in scenarios):
                # Strong penalty for non-romantic places
                if any(keyword in place_tags or keyword in place_name or keyword in place_summary 
                       for keyword in ['brewery', 'beer', 'german', 'energetic', 'casual', 'nightlife']):
                    final_vibe_score = max(0.0, final_vibe_score - 0.5)  # Strong penalty
                    # debugging via logger, not print
                    # logger.debug(f"Romantic penalty applied to {place_name}: {final_vibe_score}")
            
            scores['vibe_score'] = final_vibe_score
            
            # Novelty score
            novelty_score = 0.0
            if profile:
                # Calculate novelty based on similarity to recent likes
                novelty_score = self._calculate_novelty_score(place, profile)
            else:
                # Default novelty based on vibes
                if 'hidden_gem' in vibes or 'artsy' in vibes:
                    novelty_score = 0.7
                elif 'premium' in vibes or 'trendy' in vibes:
                    novelty_score = 0.5
                else:
                    novelty_score = 0.3
            
            scores['novelty_score'] = novelty_score
            
            # Signal boost (wow/novelty/editor/local_gem) — мягко, чтобы не ломать гео
            signal_boost = 0.0
            sig = place.get('signals') or {}
            if isinstance(sig, dict):
                wow = 0.15 if sig.get('wow_flag') else 0.0
                editor = 0.1 if sig.get('editor_pick') else 0.0
                novelty = float(sig.get('novelty_score', 0.0)) * 0.2
                local = 0.05 if sig.get('local_gem') else 0.0
                trend = float(sig.get('trend_score', 0.0)) * 0.12
                quality = float(sig.get('quality_score', 0.0)) * 0.2
                interest = float(sig.get('interest_score', 0.0)) * 0.25
                extra = 0.08 if sig.get('extraordinary') else 0.0
                raw = wow + editor + novelty + local + trend + quality + interest + extra
                mode = getattr(self, "_mode", "light")
                cap = 0.1 if mode == "light" else (0.2 if mode == "vibe" else 0.35)
                signal_boost = min(raw, cap)

            # Базовые веса — режим-зависимые
            if mode == "light":
                w_search, w_vibe, w_scen, w_exp = 0.5, 0.2, 0.2, 0.1
            elif mode == "vibe":
                w_search, w_vibe, w_scen, w_exp = 0.3, 0.4, 0.2, 0.1
            else:  # surprise
                w_search, w_vibe, w_scen, w_exp = 0.25, 0.25, 0.25, 0.25

            base_score = (
                scores['search_score'] * w_search +
                final_vibe_score * w_vibe +
                scenario_bonus * w_scen +
                0.0 * w_exp +  # experience_bonus placeholder
                signal_boost
            )

            # «Чильно»: штраф за шумные места (если в запросе присутсвуют chill/cozy и т.п.)
            if mode == "vibe" and any(v.lower() in {"chill","cozy","romantic"} for v in (vibes or [])):
                noise = 0.0
                if isinstance(sig, dict):
                    try:
                        noise = float(sig.get("noise_level", 0.0))
                    except Exception:
                        noise = 0.0
                # штраф начинается после порога 0.4
                noise_penalty = max(0.0, noise - 0.4) * 0.5  # до 0.3 примерно
                base_score -= noise_penalty
                scores['noise_penalty'] = noise_penalty
            
            scores.update({
                'vibe_score': final_vibe_score,
                'scenario_bonus': scenario_bonus,
                'experience_bonus': 0.0,  # placeholder
                'novelty_score': novelty_score,
                'signal_boost': signal_boost,
                'base_score': base_score
            })
            
            ranked.append((place, scores))
        
        # Sort by base score
        ranked.sort(key=lambda x: x[1]['base_score'], reverse=True)
        
        return ranked
    
    def _apply_vibe_alignment(self, ranked: List[Tuple[Dict[str, Any], Dict[str, float]]], 
                             vibe_pack: Dict[str, Any]) -> List[Tuple[Dict[str, Any], Dict[str, float]]]:
        """Apply vibe alignment boosts/penalties based on vibe_pack configuration."""
        if not vibe_pack:
            return ranked
        
        must_any_tags = vibe_pack.get("must_any", [])
        prefer_tags = vibe_pack.get("prefer", [])
        avoid_tags = vibe_pack.get("avoid", [])
        
        aligned = []
        
        for place, scores in ranked:
            place_tags = [t.strip().lower() for t in (place.get('tags_csv') or '').split(',') if t.strip()]
            place_name = (place.get('name') or '').lower()
            place_summary = (place.get('summary') or '').lower()
            
            # Calculate alignment score
            alignment_score = 0.0
            
            # Must_any boost: +0.1-0.2 for each match
            must_any_matches = 0
            for tag in must_any_tags:
                tag_lower = tag.lower()
                if (tag_lower in place_tags or 
                    tag_lower in place_name or 
                    tag_lower in place_summary):
                    must_any_matches += 1
            
            if must_any_tags:
                must_any_boost = min(0.2, 0.1 + (must_any_matches - 1) * 0.05)
                alignment_score += must_any_boost
            
            # Prefer boost: +0.05 for each match
            prefer_matches = 0
            for tag in prefer_tags:
                tag_lower = tag.lower()
                if (tag_lower in place_tags or 
                    tag_lower in place_name or 
                    tag_lower in place_summary):
                    prefer_matches += 1
            
            prefer_boost = prefer_matches * 0.05
            alignment_score += prefer_boost
            
            # Avoid penalty: -0.05 for each match
            avoid_matches = 0
            for tag in avoid_tags:
                tag_lower = tag.lower()
                if (tag_lower in place_tags or 
                    tag_lower in place_name or 
                    tag_lower in place_summary):
                    avoid_matches += 1
            
            avoid_penalty = avoid_matches * 0.05
            alignment_score -= avoid_penalty
            
            # Apply alignment to base score
            scores['vibe_alignment'] = alignment_score
            scores['base_score'] += alignment_score
            
            aligned.append((place, scores))
        
        return aligned
    
    def _stage2_proximity_sorting(self, ranked: List[Tuple[Dict[str, Any], Dict[str, float]]], 
                                 request: ComposeRequest) -> List[Tuple[Dict[str, Any], Dict[str, float]]]:
        """Stage 2: Proximity re-sorting using stable sort"""
        mode = getattr(self, "_mode", "light")
        
        if ranked is None:
            logger.warning("_stage2_proximity_sorting received None ranked")
            return []
        
        if (request.user_lat is None) or (request.user_lng is None):
            return ranked
        
        def distance_km(place: Dict[str, Any]) -> float:
            """Calculate distance from user to place"""
            lat = place.get('lat')
            lng = place.get('lng')
            if (lat is None) or (lng is None):
                return float('inf')
            
            # Haversine formula
            lat1, lng1 = math.radians(request.user_lat), math.radians(request.user_lng)
            lat2, lng2 = math.radians(lat), math.radians(lng)
            
            dlat = lat2 - lat1
            dlng = lng2 - lng1
            
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
            c = 2 * math.asin(math.sqrt(a))
            
            return 6371 * c  # Earth radius in km
        
        # Create list with distances
        ranked_with_distance = [(place, scores, distance_km(place)) for place, scores in ranked]
        
        # compute final_score with proximity bonus
        for i, (place, scores, distance) in enumerate(ranked_with_distance):
            if distance < float('inf'):
                # режим "light" — сильнее гео, "surprise" — слабее
                base = 0.35 if mode == "light" else (0.25 if mode == "vibe" else 0.18)
                proximity_bonus = base * math.exp(-distance / 2.0)  # distance в КМ
                scores['proximity_bonus'] = proximity_bonus
                scores['final_score'] = scores['base_score'] + proximity_bonus
            else:
                scores['proximity_bonus'] = 0.0
                scores['final_score'] = scores['base_score']

        # Stable sort: по убыванию final_score, при равенстве — ближе выше
        ranked_with_distance = sorted(
            ranked_with_distance,
            key=lambda x: (-x[1].get('final_score', x[1].get('base_score', 0.0)), x[2])
        )
        
        return [(place, scores) for place, scores, _ in ranked_with_distance]
    
    def _stage3_diversity(self, ranked: List[Tuple[Dict[str, Any], Dict[str, float]]], 
                         top_k: int = 12) -> List[Tuple[Dict[str, Any], Dict[str, float]]]:
        """Stage 3: MMR diversity to avoid similar results"""
        if ranked is None:
            logger.warning("_stage3_diversity received None ranked")
            return []
        
        if len(ranked) <= top_k:
            return ranked
        
        selected = []
        remaining = ranked.copy()
        
        # Select first item (highest score)
        if remaining:
            selected.append(remaining.pop(0))
        
        # MMR selection
        while len(selected) < top_k and remaining:
            best_item = None
            best_score = -1
            best_idx = -1
            
            for i, (place, scores) in enumerate(remaining):
                # Calculate MMR score
                relevance = scores.get('final_score', scores.get('base_score', 0))
                diversity = self._calculate_diversity(place, selected)
                
                mmr_score = 0.7 * relevance + 0.3 * diversity
                
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_item = (place, scores)
                    best_idx = i
            
            if best_item:
                selected.append(best_item)
                remaining.pop(best_idx)
            else:
                break
        
        return selected
    
    def _calculate_diversity(self, place: Dict[str, Any], selected: List[Tuple[Dict[str, Any], Dict[str, float]]]) -> float:
        """Calculate diversity score for MMR"""
        if not selected:
            return 1.0
        
        # Calculate similarity to selected places
        similarities = []
        for selected_place, _ in selected:
            similarity = self._calculate_place_similarity(place, selected_place)
            similarities.append(similarity)
        
        # Diversity is inverse of max similarity
        max_similarity = max(similarities) if similarities else 0
        return 1.0 - max_similarity
    
    def _calculate_place_similarity(self, place1: Dict[str, Any], place2: Dict[str, Any]) -> float:
        """Calculate similarity between two places"""
        # Use bitset similarity if available
        tag_bitset1 = place1.get('tag_bitset')
        tag_bitset2 = place2.get('tag_bitset')
        if tag_bitset1 and tag_bitset2:
            return self.bitset_service.calculate_vibe_score(tag_bitset1, tag_bitset2)
        
        # Fallback to category similarity
        category1 = place1.get('category')
        category2 = place2.get('category')
        if category1 is None and category2 is None:
            return 0.1
        if category1 == category2 and category1 is not None:
            return 0.8
        if category1 and category2:
            return 0.3
        return 0.1
    
    def _calculate_novelty_score(self, place: Dict[str, Any], profile: SessionProfile) -> float:
        """Calculate novelty score based on profile history"""
        if not profile.signals:
            return 0.5  # Default novelty
        
        # Get recent liked places
        recent_likes = [
            signal for signal in profile.signals[-10:]  # Last 10 signals
            if signal.get('action') == 'like'
        ]
        
        if not recent_likes:
            return 0.5
        
        # Calculate similarity to recent likes
        similarities = []
        for signal in recent_likes:
            # This would need place data - simplified for now
            similarity = 0.3  # Placeholder
            similarities.append(similarity)
        
        avg_similarity = sum(similarities) / len(similarities) if similarities else 0
        novelty = profile.novelty_preference * (1 - avg_similarity)
        
        return min(novelty, 1.0)
    
    def _convert_to_place_cards(self, ranked: List[Tuple[Dict[str, Any], Dict[str, float]]], 
                               request: ComposeRequest) -> List[PlaceCard]:
        """Convert ranked places to PlaceCard objects"""
        if ranked is None:
            logger.warning("_convert_to_place_cards received None ranked")
            return []
        
        cards = []
        
        for place, scores in ranked:
            # Calculate distance if user location available
            distance_m = None
            walk_time_min = None
            
            lat = place.get('lat')
            lng = place.get('lng')
            if (request.user_lat is not None) and (request.user_lng is not None) and (lat is not None) and (lng is not None):
                distance_m = self._calculate_distance_m(request.user_lat, request.user_lng, lat, lng)
                walk_time_min = int(distance_m / 80)  # 80m/min walking speed
            
            card = PlaceCard(
                id=place.get('id', 0),
                name=place.get('name', "Unknown"),
                summary=place.get('summary', place.get('description_full', "")),
                tags_csv=place.get('tags_csv', ""),
                category=place.get('category') or "general",
                lat=lat or 0.0,
                lng=lng or 0.0,
                address=place.get('address'),
                picture_url=place.get('picture_url'),
                website=place.get('website'),
                phone=place.get('phone'),
                price_level=place.get('price_level'),
                distance_m=distance_m,
                walk_time_min=walk_time_min,
                search_score=scores.get('search_score', 0.0),
                vibe_score=scores.get('vibe_score', 0.0),
                novelty_score=scores.get('novelty_score', 0.0)
            )
            cards.append(card)
        
        return cards
    
    def _calculate_distance_m(self, lat1: float, lng1: float, lat2: float, lng2: float) -> int:
        """Calculate distance in meters using Haversine formula"""
        lat1, lng1 = math.radians(lat1), math.radians(lng1)
        lat2, lng2 = math.radians(lat2), math.radians(lng2)
        
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return int(6371000 * c)  # Earth radius in meters
    
    def _get_rail_label(self, step: str) -> str:
        """Get human-readable label for rail step"""
        labels = {
            'restaurant': 'Where to eat',
            'activity': 'What to do',
            'drinks': 'Where to drink',
            'wellness': 'Wellness & Spa',
            'culture': 'Culture & Arts',
            'shopping': 'Shopping',
            'general': 'Places to visit'
        }
        return labels.get(step, 'Places to visit')


def create_ranking_service(bitset_service: BitsetService, search_service: SearchService = None) -> RankingService:
    """Create ranking service with dependencies"""
    return RankingService(bitset_service, search_service)
