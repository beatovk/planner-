#!/usr/bin/env python3
"""Search service with FTS5 integration and query sanitization"""

import re
import json
import math
import hashlib
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from functools import lru_cache
from collections import OrderedDict
from sqlalchemy.orm import Session
from sqlalchemy import text
from apps.places.models import Place
from apps.places.schemas.slots import Slot, SlotType

logger = logging.getLogger(__name__)


class QueryIntent(Enum):
    """Search intent classification"""
    VIBE = "vibe"           # chill, dating, rooftop, cozy
    FEATURE = "feature"     # tom yum, brunch, craft beer, vegan
    NAVIGATIONAL = "navigational"  # exact names, malls, brands
    AREA = "area"           # district, street, "near me"
    MIXED = "mixed"         # combination of intents
    DEFAULT = "default"     # fallback


class QueryBuilder:
    """Query builder with FTS5 syntax sanitization and normalization"""
    
    def __init__(self):
        # Synonyms dictionary (можно расширять из YAML)
        base_syn = {
            "tom": ["tom"],
            "yum": ["yam"],
            "rooftop": ["roof-top", "roof top"],
            "cafe": ["café", "coffee"],
            "restaurant": ["resto", "dining"],
            "bar": ["pub", "lounge"],
            "thai": ["thailand", "thailandese"],
            "bangkok": ["bkk", "krung thep"],
            "climb": ["climbing", "climbing gym", "bouldering"],
            "cinema": ["movie", "movies", "movie theater", "movie theatre", "theater", "theatre"],
            "pasta": ["tagliatelle", "spaghetti", "rigatoni"],
            "date": ["date night", "romantic", "anniversary"],
            "dating": ["date night", "romantic"],
            "romantic": ["date night", "date"],
        }
        self.synonyms = base_syn
        try:
            import os, yaml
            path = os.path.join(os.getcwd(), "config", "synonyms.yml")
            if os.path.exists(path):
                cfg = yaml.safe_load(open(path, "r", encoding="utf-8"))
                for k, arr in (cfg.get("synonyms") or {}).items():
                    k0 = k.strip().lower()
                    self.synonyms.setdefault(k0, [])
                    self.synonyms[k0] = list({*self.synonyms[k0], *[a.strip().lower() for a in arr if a]})
        except Exception:
            pass
        
        # Intent detection dictionaries
        self.vibe_tokens = {
            "chill", "cozy", "romantic", "dating", "date", "intimate", "relaxed",
            "rooftop", "roof-top", "jazz", "live music", "ambient", "atmospheric",
            "vibe", "mood", "atmosphere", "ambience", "chill out", "hangout"
        }
        
        self.feature_tokens = {
            "tom yum", "tom yam", "brunch", "breakfast", "lunch", "dinner",
            "craft beer", "beer", "wine", "cocktail", "coffee", "tea",
            "vegan", "vegetarian", "halal", "gluten-free", "organic",
            "buffet", "bbq", "grill", "sushi", "pizza", "pasta", "burger",
            "thai", "thailand", "spicy", "curry", "noodles", "rice",
            "seafood", "fish", "chicken", "beef", "pork", "vegetables"
        }
        
        self.navigational_tokens = {
            "emporium", "central", "siam", "paragon", "terminal21", "mbk",
            "chatuchak", "asiatique", "icon", "river", "mall", "center",
            "starbucks", "mcdonalds", "kfc", "pizza hut", "subway"
        }
        
        self.area_tokens = {
            "sukhumvit", "silom", "siam", "chatuchak", "chinatown", "yaowarat",
            "thonglor", "ekkamai", "phrom phong", "asok", "nana", "ploenchit",
            "ari", "phaya thai", "victory monument", "near me", "nearby", "close"
        }
        
        # Generic tokens that should be deflated (reduced weight)
        self.generic_tokens = {
            "cafe", "restaurant", "bar", "place", "food", "drink", "eat", "drink",
            "shop", "store", "mall", "center", "area", "district", "street"
        }
    
    def detect_intent(self, query: str) -> QueryIntent:
        """Detect search intent based on query tokens and phrases"""
        if not query or not query.strip():
            return QueryIntent.DEFAULT
            
        query_lower = query.lower().strip()
        tokens = self.normalize_tokens(query)
        
        # Check for multi-word phrases first
        phrase_matches = {
            'vibe': 0,
            'feature': 0,
            'navigational': 0,
            'area': 0
        }
        
        # Check for phrases in the original query
        for phrase in ['tom yum', 'tom yam', 'craft beer', 'live music', 'roof top', 'roof-top']:
            if phrase in query_lower:
                if phrase in ['tom yum', 'tom yam', 'craft beer']:
                    phrase_matches['feature'] += 1
                elif phrase in ['live music', 'roof top', 'roof-top']:
                    phrase_matches['vibe'] += 1
        
        # Count intent signals from individual tokens
        vibe_count = sum(1 for token in tokens if token in self.vibe_tokens) + phrase_matches['vibe']
        feature_count = sum(1 for token in tokens if token in self.feature_tokens) + phrase_matches['feature']
        navigational_count = sum(1 for token in tokens if token in self.navigational_tokens) + phrase_matches['navigational']
        area_count = sum(1 for token in tokens if token in self.area_tokens) + phrase_matches['area']
        
        # Check for mixed intents (multiple categories)
        intent_counts = [vibe_count, feature_count, navigational_count, area_count]
        non_zero_intents = sum(1 for count in intent_counts if count > 0)
        
        if non_zero_intents > 1:
            return QueryIntent.MIXED
        
        # Single intent detection
        if navigational_count > 0:
            return QueryIntent.NAVIGATIONAL
        elif vibe_count > 0:
            return QueryIntent.VIBE
        elif feature_count > 0:
            return QueryIntent.FEATURE
        elif area_count > 0:
            return QueryIntent.AREA
        else:
            return QueryIntent.DEFAULT
    
    # NEW: canonical 3-slot extraction using CANON_SLOTS configuration
    def build_slots(self, query: str) -> list:
        """
        Return up to 3 canonical slots from free-text using CANON_SLOTS, e.g.:
        "gallery, tea, sushi" -> ["experience:gallery","drink:tea","dish:sushi"]
        """
        if not query or not query.strip():
            return []
        
        # Import CANON_SLOTS
        try:
            from config.canon_slots import CANON_SLOTS
        except ImportError:
            # Fallback to old logic if config not found
            return self._build_slots_fallback(query)
        
        # Split query by commas and clean
        query_parts = [part.strip().lower() for part in query.split(',') if part.strip()]
        
        slots = []
        for part in query_parts:
            # Direct match in CANON_SLOTS
            if part in CANON_SLOTS:
                slot_config = CANON_SLOTS[part]
                slot_key = f"{slot_config['kind']}:{part}"
                slots.append(slot_key)
            else:
                # Try to find partial matches
                for canon_key, slot_config in CANON_SLOTS.items():
                    if canon_key in part or part in canon_key:
                        slot_key = f"{slot_config['kind']}:{canon_key}"
                        if slot_key not in slots:  # avoid duplicates
                            slots.append(slot_key)
                        break
        
        # Cap at 3 slots
        return slots[:3]
    
    def _build_slots_fallback(self, query: str) -> list:
        """Fallback to old hardcoded slots if CANON_SLOTS not available"""
        q = query.lower()
        slots = []
        def _has_any(keys): return any(k in q for k in keys)
        # 1) dish: tom_yum
        if _has_any(["tom yum","tom-yum","tomyum","tom yam","tom-yam"]):
            slots.append("dish:tom_yum")
        # 2) experience: rooftop
        if _has_any(["rooftop","roof top","roof-top","skybar","sky bar","sky-bar"]):
            slots.append("experience:rooftop")
        # 3) park walk
        if _has_any(["park","promenade","waterfront","riverside","riverfront","boardwalk","garden","botanical"]):
            slots.append("experience:park_stroll")
        # de-dup and cap 3
        out = []
        for s in slots:
            if s not in out:
                out.append(s)
            if len(out) == 3: break
        return out
    
    def get_weights_for_intent(self, intent: QueryIntent) -> Tuple[float, ...]:
        """Get BM25 weights based on search intent"""
        # Weights: [name, tags_csv, summary, category, description_full, address]
        
        if intent == QueryIntent.VIBE:
            # Vibe/Experience: focus on tags and summary
            return (2.0, 9.0, 7.0, 2.0, 3.0, 0.5)
        elif intent == QueryIntent.FEATURE:
            # Feature/Cuisine: focus on tags and description
            return (3.0, 8.0, 5.0, 2.0, 6.0, 0.5)
        elif intent == QueryIntent.NAVIGATIONAL:
            # Navigational/Entity: focus on name and address
            return (8.0, 4.0, 2.0, 1.0, 1.0, 4.0)
        elif intent == QueryIntent.AREA:
            # Area/Proximity: focus on address and tags
            return (2.0, 5.0, 3.0, 2.0, 1.0, 7.0)
        elif intent == QueryIntent.MIXED:
            # Mixed: balanced approach
            return (4.0, 6.0, 5.0, 2.0, 3.0, 2.0)
        else:  # DEFAULT
            # Universal profile: balanced with slight preference for tags
            return (3.0, 7.0, 6.0, 2.0, 2.0, 1.0)
    
    def normalize_tokens(self, query: str) -> List[str]:
        """Normalize and tokenize search query"""
        if not query or not query.strip():
            return []
        
        # Convert to lowercase and strip whitespace
        query = query.lower().strip()
        
        # Remove special characters except spaces and basic punctuation
        query = re.sub(r'[^\w\s\-]', ' ', query)
        
        # Split by whitespace and filter empty tokens
        tokens = [token.strip() for token in query.split() if token.strip()]
        
        return tokens
    
    def escape_fts5_query(self, token: str) -> str:
        """Escape special FTS5 characters in a token"""
        # Escape double quotes and asterisks
        token = token.replace('"', '""')
        token = token.replace('*', '')
        
        # Wrap in quotes to handle spaces and special characters
        return f'"{token}"'
    
    def build_match_query(self, query: str) -> str:
        """Build FTS5 MATCH query with smart Netflix-style search"""
        tokens = self.normalize_tokens(query)
        
        if not tokens:
            return '*'
        
        # Netflix-style search: prioritize exact matches, then partial matches
        parts = []
        
        for token in tokens:
            # Get synonyms for this token
            alternatives = [token]
            if token in self.synonyms:
                alternatives.extend(self.synonyms[token])
            
            # Create OR group for alternatives with different matching strategies
            token_parts = []
            
            for alt in alternatives:
                # Exact match (highest priority)
                token_parts.append(f'"{alt}"')
                
                # Prefix match for longer tokens
                if len(alt) >= 3:
                    token_parts.append(f'"{alt}"*')
                
                # Partial match for compound words
                if ' ' in alt:
                    words = alt.split()
                    for word in words:
                        if len(word) >= 3:
                            token_parts.append(f'"{word}"*')
            
            # Join alternatives with OR
            if len(token_parts) == 1:
                parts.append(token_parts[0])
            else:
                parts.append(f"({' OR '.join(token_parts)})")
        
        # Join all tokens with AND
        return " AND ".join(parts)


class SearchService:
    """Search service with FTS5 integration and BM25 ranking"""
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db
        self.query_builder = QueryBuilder()
        # Cache for search results (LRU ~100 entries, TTL 5 minutes)
        self._search_cache = OrderedDict()
        self._cache_ttl = 300  # 5 minutes
        self._cache_max_entries = 100

    def bind_db(self, db: Session) -> "SearchService":
        """Bind/replace DB session for this service (per-request)."""
        self.db = db
        return self
    
    def _cache_set(self, key: str, value: Any) -> None:
        now = time.time()
        entry = {"value": value, "timestamp": now}
        if key in self._search_cache:
            self._search_cache.pop(key, None)
        self._search_cache[key] = entry
        # LRU eviction
        while len(self._search_cache) > self._cache_max_entries:
            self._search_cache.popitem(last=False)

    def _cache_get(self, key: str) -> Optional[Any]:
        entry = self._search_cache.get(key)
        if not entry:
            return None
        if (time.time() - entry["timestamp"]) > self._cache_ttl:
            self._search_cache.pop(key, None)
            return None
        # bump LRU
        self._search_cache.move_to_end(key, last=True)
        return entry["value"]
    
    def _build_tsquery(self, query: str) -> str:
        """Build enriched tsquery string with synonym/morph expansions for FTS."""
        raw = (query or "").strip()
        if not raw:
            return ""

        tokens = self.query_builder.normalize_tokens(raw)
        if not tokens:
            return raw

        groups: List[List[str]] = []
        seen_variants: set[str] = set()

        for token in tokens:
            variants: List[str] = []

            def _add_variant(text: str) -> None:
                cleaned = (text or "").strip().lower()
                if not cleaned:
                    return
                if cleaned in seen_variants:
                    return
                seen_variants.add(cleaned)
                variants.append(cleaned)

            _add_variant(token)

            entry = self.query_builder.synonyms.get(token)
            if entry:
                _add_variant(entry.canonical.replace("_", " "))
                for syn in entry.synonyms:
                    _add_variant(syn)

            groups.append(variants or [token])

        parts: List[str] = []
        for variants in groups:
            if not variants:
                continue
            # websearch_to_tsquery treats OR, AND; wrap multi-variant group in parentheses
            sanitized = [v.replace('"', ' ') for v in variants]
            if len(sanitized) == 1:
                parts.append(sanitized[0])
            else:
                parts.append("(" + " OR ".join(sanitized) + ")")

        ts_query = " ".join(parts).strip()
        if not ts_query:
            ts_query = raw

        if ts_query != raw:
            logger.debug("FTS tsquery expanded '%s' -> '%s'", raw, ts_query)

        return ts_query
    
    
    def _get_cache_key(self, query: str, user_lat: Optional[float], user_lng: Optional[float],
                      radius_m: Optional[int], limit: int, offset: int, area: Optional[str] = None,
                      sort: str = "relevance") -> str:
        """Generate cache key for search parameters"""
        # time-bucket (2h) чтобы не кэшировать навсегда «вчерашний вечер»
        import time as _t
        tb = int(_t.time() // (2 * 3600))
        key = f"{(query or '').strip().lower()}|{round(user_lat or 0.0,4)}|{round(user_lng or 0.0,4)}|{radius_m}|{limit}|{offset}|{(area or '').strip().lower()}|{sort}|tb={tb}"
        return hashlib.md5(key.encode()).hexdigest()
    
    
    def _get_recent_places(
        self, 
        limit: int = 20, 
        offset: int = 0,
        user_lat: Optional[float] = None,
        user_lng: Optional[float] = None,
        radius_m: Optional[int] = None,
        sort: str = "relevance"
    ) -> List[Dict[str, Any]]:
        """Get recent published places when no search query provided"""
        
        
        # Use SQLAlchemy ORM for simplicity
        query = self.db.query(Place).filter(
            Place.processing_status.in_(['published', 'summarized', 'new'])
        )
        
        # Pre-filter по bbox (PostgreSQL-friendly)
        if (user_lat is not None) and (user_lng is not None) and (radius_m is not None):
            min_lat, max_lat, min_lng, max_lng = self._get_geo_bbox(user_lat, user_lng, radius_m)
            query = query.filter(Place.lat.between(min_lat, max_lat), Place.lng.between(min_lng, max_lng))
        
        # Get all places first (no limit yet)
        places = query.all()
        
        # Convert to dict format with distance calculation
        results = []
        for place in places:
            place_dict = self._place_to_dict(place, user_lat, user_lng)
            results.append(place_dict)
        
        # Post-filter по фактической дистанции и сортировка
        if (user_lat is not None) and (user_lng is not None) and (radius_m is not None):
            results = [r for r in results if r.get('distance_m') is not None and r['distance_m'] <= radius_m]

        if sort == "distance" and (user_lat is not None) and (user_lng is not None):
            # Sort by distance (closest first)
            results.sort(key=lambda x: x.get('distance_m', float('inf')))
        else:
            # Sort by updated date (newest first)
            results.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
        
        # Apply offset and limit
        return results[offset:offset + limit]
    
    def _netflix_style_search(
        self, 
        query: str, 
        limit: int, 
        offset: int,
        user_lat: Optional[float] = None,
        user_lng: Optional[float] = None,
        radius_m: Optional[int] = None,
        sort: str = "relevance",
        area: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Netflix-style search with multiple strategies and intelligent ranking"""
        
        # Get area viewport bounds if area is specified
        area_bounds = None
        if area:
            from apps.places.services.district_cache import district_cache
            area_bounds = district_cache.get_viewport(area)
            logger.debug(f"Area '{area}' viewport: {area_bounds}")
            # fail-open: если нет viewport — продолжаем без area-фильтра
        
        # Normalize query
        query_lower = query.lower().strip()
        tokens = self.query_builder.normalize_tokens(query)
        
        # Strategy 1: Exact matches (highest priority)
        exact_matches = self._search_exact_matches(query_lower, user_lat, user_lng, radius_m, area_bounds)
        
        # Strategy 2: Name matches (high priority)
        name_matches = self._search_name_matches(query_lower, tokens, user_lat, user_lng, radius_m, area_bounds)
        
        # Strategy 3: Tag matches (medium priority)
        tag_matches = self._search_tag_matches(query_lower, tokens, user_lat, user_lng, radius_m, area_bounds)
        
        # Strategy 4: Description matches (lower priority)
        desc_matches = self._search_description_matches(query_lower, tokens, user_lat, user_lng, radius_m, area_bounds)
        
        # Strategy 5: Fuzzy matches (lowest priority)
        fuzzy_matches = self._search_fuzzy_matches(query_lower, tokens, user_lat, user_lng, radius_m, area_bounds)
        
        # Combine and rank results (без повторных ORM-запросов и с уже посчитанной дистанцией)
        all_results = {}
        
        # Add results with different weights and ensure distance is calculated
        for place in exact_matches:
            candidate = dict(place)
            candidate['search_score'] = 1000
            all_results[place['id']] = candidate
        
        for place in name_matches:
            if place['id'] not in all_results:
                candidate = dict(place)
                candidate['search_score'] = 800
                all_results[place['id']] = candidate
            else:
                all_results[place['id']]['search_score'] += 200
        
        for place in tag_matches:
            if place['id'] not in all_results:
                candidate = dict(place)
                candidate['search_score'] = 600
                all_results[place['id']] = candidate
            else:
                all_results[place['id']]['search_score'] += 150
        
        for place in desc_matches:
            if place['id'] not in all_results:
                candidate = dict(place)
                candidate['search_score'] = 400
                all_results[place['id']] = candidate
            else:
                all_results[place['id']]['search_score'] += 100
        
        for place in fuzzy_matches:
            if place['id'] not in all_results:
                candidate = dict(place)
                candidate['search_score'] = 200
                all_results[place['id']] = candidate
            else:
                all_results[place['id']]['search_score'] += 50
        
        # Distance calculation is handled in _place_to_dict
        
        # Apply area filtering to final results if specified
        if area_bounds:
            filtered_results = {}
            for place_id, place_data in all_results.items():
                lat = place_data.get('lat')
                lng = place_data.get('lng')
                if (lat and lng and 
                    area_bounds['lat_min'] <= lat <= area_bounds['lat_max'] and
                    area_bounds['lng_min'] <= lng <= area_bounds['lng_max']):
                    filtered_results[place_id] = place_data
            all_results = filtered_results
            logger.debug(f"Area filtering applied - {len(all_results)} places remain")
        
        # Радиус на финальном множестве
        if (user_lat is not None) and (user_lng is not None) and (radius_m is not None):
            all_results = {pid: p for pid, p in all_results.items()
                           if p.get('distance_m') is not None and p['distance_m'] <= radius_m}

        # Sort by search score or distance
        if sort == "distance" and user_lat and user_lng:
            # Sort by distance (closest first)
            sorted_results = sorted(all_results.values(), key=lambda x: x.get('distance_m', float('inf')))
        else:
            # Sort by search score (highest first)
            sorted_results = sorted(all_results.values(), key=lambda x: x['search_score'], reverse=True)
        
        # Cache results
        cache_key = self._get_cache_key(query, user_lat, user_lng, radius_m, limit, offset, area, sort)
        self._search_cache[cache_key] = {
            'results': sorted_results[offset:offset + limit],
            'timestamp': time.time()
        }
        
        return sorted_results[offset:offset + limit]

    def _fts_search(
        self,
        query: str,
        limit: int,
        offset: int,
        user_lat: Optional[float] = None,
        user_lng: Optional[float] = None,
        area: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Primary FTS5 search with BM25 and intent-based field weights."""
        if not self.db:
            return []
        # Intent (зарезервировано под веса на будущее)
        _ = self.query_builder.detect_intent(query)

        # Готовим area + bbox для биндов
        params = {"q": query, "limit": limit, "offset": offset}
        area_sql = ""
        if area:
            from apps.places.services.district_cache import district_cache
            area_bounds = district_cache.get_viewport(area)
            if area_bounds:
                area_sql += " AND m.lat BETWEEN :a_lat_min AND :a_lat_max AND m.lng BETWEEN :a_lng_min AND :a_lng_max "
                params.update({
                    "a_lat_min": area_bounds["lat_min"], "a_lat_max": area_bounds["lat_max"],
                    "a_lng_min": area_bounds["lng_min"], "a_lng_max": area_bounds["lng_max"],
                })
        # bbox вокруг пользователя (если есть)
        if (user_lat is not None) and (user_lng is not None):
            # Мягкий bbox на 10км, чтобы ограничить выборку даже без radius_m
            min_lat, max_lat, min_lng, max_lng = self._get_geo_bbox(user_lat, user_lng, 10000)
            area_sql += " AND m.lat BETWEEN :u_lat_min AND :u_lat_max AND m.lng BETWEEN :u_lng_min AND :u_lng_max "
            params.update({
                "u_lat_min": min_lat, "u_lat_max": max_lat,
                "u_lng_min": min_lng, "u_lng_max": max_lng,
            })

        # Поиск по материализованному представлению с tsvector
        sql = text(f"""
            SELECT 
                m.id, m.name, m.category, m.summary, m.tags_csv,
                m.lat, m.lng, m.picture_url, m.gmaps_place_id, m.gmaps_url, m.rating,
                m.processing_status,
                ts_rank(m.search_vector, websearch_to_tsquery('simple', :q)) AS rank_score
            FROM epx.places_search_mv m
            WHERE m.processing_status IN ('published','summarized','new')
              AND m.search_vector @@ websearch_to_tsquery('simple', :q)
              {area_sql}
            ORDER BY rank_score DESC
            LIMIT :limit OFFSET :offset
        """)

        rows = self.db.execute(sql, params)

        results: List[Dict[str, Any]] = []
        for row in rows:
            m = row._mapping
            place = {
                "id": m["id"],
                "name": m["name"],
                "category": m["category"],
                "summary": m["summary"],
                "tags_csv": m["tags_csv"],
                "lat": m["lat"],
                "lng": m["lng"],
                "picture_url": m["picture_url"],
                "gmaps_place_id": m["gmaps_place_id"],
                "gmaps_url": m["gmaps_url"],
                "rating": m["rating"],
                "processing_status": m["processing_status"],
                "rank": 0.0,
            }
            rank_score = float(m["rank_score"] or 0.0)
            # Higher is better downstream; normalize to ~[0..1000]
            place["search_score"] = int(rank_score * 1000)

            if (
                user_lat is not None and user_lng is not None
                and place["lat"] is not None and place["lng"] is not None
            ):
                dist = self._haversine_m(user_lat, user_lng, place["lat"], place["lng"])
                place["distance_m"] = int(dist)
                place["walk_time_min"] = int(dist / 80)
            results.append(place)
        return results
    
    def _search_exact_matches(self, query: str, user_lat: Optional[float], user_lng: Optional[float], radius_m: Optional[int], area_bounds: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
        """Search for exact matches in name"""
        query_obj = self.db.query(Place).filter(
            Place.processing_status.in_(['published', 'summarized', 'new']),
            Place.name.ilike(f'%{query}%')
        )
        
        # Apply area filtering if specified
        if area_bounds:
            before_count = query_obj.count()
            query_obj = query_obj.filter(
                Place.lat.between(area_bounds['lat_min'], area_bounds['lat_max']),
                Place.lng.between(area_bounds['lng_min'], area_bounds['lng_max'])
            )
            after_count = query_obj.count()
            logger.debug("Exact matches area filter: before=%d after=%d", before_count, after_count)
        
        places = query_obj.limit(10).all()
        return [self._place_to_dict(p, user_lat, user_lng) for p in places]
    
    def _search_name_matches(self, query: str, tokens: List[str], user_lat: Optional[float], user_lng: Optional[float], radius_m: Optional[int], area_bounds: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
        """Search for matches in name with token matching"""
        from sqlalchemy import or_, func
        
        conditions = []
        for token in tokens:
            conditions.append(Place.name.ilike(f'%{token}%'))
        
        query_obj = self.db.query(Place).filter(
            Place.processing_status.in_(['published', 'summarized', 'new']),
            or_(*conditions)
        )
        
        # Apply area filtering if specified
        if area_bounds:
            query_obj = query_obj.filter(
                Place.lat.between(area_bounds['lat_min'], area_bounds['lat_max']),
                Place.lng.between(area_bounds['lng_min'], area_bounds['lng_max'])
            )
        
        places = query_obj.limit(15).all()
        return [self._place_to_dict(p, user_lat, user_lng) for p in places]
    
    def _search_tag_matches(self, query: str, tokens: List[str], user_lat: Optional[float], user_lng: Optional[float], radius_m: Optional[int], area_bounds: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
        """Search for matches in tags"""
        from sqlalchemy import or_, func
        
        conditions = []
        for token in tokens:
            conditions.append(Place.tags_csv.ilike(f'%{token}%'))
        
        query_obj = self.db.query(Place).filter(
            Place.processing_status.in_(['published', 'summarized', 'new']),
            or_(*conditions)
        )
        
        # Apply area filtering if specified
        if area_bounds:
            query_obj = query_obj.filter(
                Place.lat.between(area_bounds['lat_min'], area_bounds['lat_max']),
                Place.lng.between(area_bounds['lng_min'], area_bounds['lng_max'])
            )
        
        places = query_obj.limit(20).all()
        return [self._place_to_dict(p, user_lat, user_lng) for p in places]
    
    def _search_description_matches(self, query: str, tokens: List[str], user_lat: Optional[float], user_lng: Optional[float], radius_m: Optional[int], area_bounds: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
        """Search for matches in description/summary"""
        from sqlalchemy import or_, func
        
        conditions = []
        for token in tokens:
            conditions.append(Place.summary.ilike(f'%{token}%'))
        
        query_obj = self.db.query(Place).filter(
            Place.processing_status.in_(['published', 'summarized', 'new']),
            or_(*conditions)
        )
        
        # Apply area filtering if specified
        if area_bounds:
            query_obj = query_obj.filter(
                Place.lat.between(area_bounds['lat_min'], area_bounds['lat_max']),
                Place.lng.between(area_bounds['lng_min'], area_bounds['lng_max'])
            )
        
        places = query_obj.limit(25).all()
        return [self._place_to_dict(p, user_lat, user_lng) for p in places]
    
    def _search_fuzzy_matches(self, query: str, tokens: List[str], user_lat: Optional[float], user_lng: Optional[float], radius_m: Optional[int], area_bounds: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
        """Search for fuzzy matches using synonyms and partial matching"""
        from sqlalchemy import or_, func
        
        # Get synonyms for all tokens
        all_terms = set(tokens)
        for token in tokens:
            if token in self.query_builder.synonyms:
                all_terms.update(self.query_builder.synonyms[token])
        
        conditions = []
        for term in all_terms:
            conditions.extend([
                Place.name.ilike(f'%{term}%'),
                Place.tags_csv.ilike(f'%{term}%'),
                Place.summary.ilike(f'%{term}%')
            ])
        
        query_obj = self.db.query(Place).filter(
            Place.processing_status.in_(['published', 'summarized', 'new']),
            or_(*conditions)
        )
        
        # Apply area filtering if specified
        if area_bounds:
            query_obj = query_obj.filter(
                Place.lat.between(area_bounds['lat_min'], area_bounds['lat_max']),
                Place.lng.between(area_bounds['lng_min'], area_bounds['lng_max'])
            )
        
        places = query_obj.limit(30).all()
        return [self._place_to_dict(p, user_lat, user_lng) for p in places]
    
    def _place_to_dict(self, place: Place, user_lat: Optional[float] = None, user_lng: Optional[float] = None) -> Dict[str, Any]:
        """Convert Place object to dictionary with distance calculation"""
        place_dict = {
            'id': place.id,
            'name': place.name,
            'category': place.category,
            'summary': place.summary,
            'tags_csv': place.tags_csv,
            'lat': place.lat,
            'lng': place.lng,
            'picture_url': place.picture_url,
            'gmaps_place_id': place.gmaps_place_id,
            'gmaps_url': place.gmaps_url,
            'rating': place.rating,
            'processing_status': place.processing_status,
            'rank': 0.0
        }
        
        # Add distance if geo filtering was used
        if (
            user_lat is not None and user_lng is not None
            and place.lat is not None and place.lng is not None
        ):
            distance = self._haversine_m(user_lat, user_lng, place.lat, place.lng)
            place_dict['distance_m'] = int(distance)
            place_dict['walk_time_min'] = int(distance / 80)  # 80 m/min walking speed
        
        return place_dict

    def _haversine_m(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Numerically stable Haversine distance in meters."""
        import math
        rlat1, rlng1 = math.radians(lat1), math.radians(lng1)
        rlat2, rlng2 = math.radians(lat2), math.radians(lng2)
        dlat = rlat2 - rlat1
        dlng = rlng2 - rlng1
        a = math.sin(dlat/2)**2 + math.cos(rlat1)*math.cos(rlat2)*math.sin(dlng/2)**2
        c = 2 * math.asin(min(1.0, math.sqrt(a)))
        return 6371000.0 * c

    def _get_geo_bbox(self, lat: float, lng: float, radius_m: float) -> Tuple[float, float, float, float]:
        """Get bounding box for geo filtering (lat_min, lat_max, lng_min, lng_max)."""
        import math
        # Earth radius in meters
        R = 6371000.0
        # Convert radius to degrees (approximate)
        lat_delta = radius_m / R * (180.0 / math.pi)
        lng_delta = radius_m / (R * math.cos(math.radians(lat))) * (180.0 / math.pi)
        
        return (
            lat - lat_delta,  # lat_min
            lat + lat_delta,  # lat_max
            lng - lng_delta,  # lng_min
            lng + lng_delta   # lng_max
        )
    
    def _build_area_filter_sql(self, area_bounds: Optional[Dict[str, float]]) -> str:
        """Build SQL filter for area bounds"""
        if not area_bounds:
            return ""
        return (
            f" AND p.lat BETWEEN {area_bounds['lat_min']} AND {area_bounds['lat_max']} "
            f"AND p.lng BETWEEN {area_bounds['lng_min']} AND {area_bounds['lng_max']} "
        )
    
    def search_places_with_slot(
        self,
        slot_key: str,
        limit: int = 20,
        offset: int = 0,
        user_lat: Optional[float] = None,
        user_lng: Optional[float] = None,
        radius_m: Optional[int] = None,
        area: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search places using CANON_SLOTS configuration for targeted filtering"""
        try:
            from config.canon_slots import CANON_SLOTS
        except ImportError:
            # Fallback to regular search if config not found
            slot_name = slot_key.split(':', 1)[-1] if ':' in slot_key else slot_key
            return self.search_places(slot_name, limit, offset, user_lat, user_lng, radius_m, "relevance", area)
        
        # Extract slot name from slot_key (e.g., "experience:gallery" -> "gallery")
        slot_name = slot_key.split(':', 1)[-1] if ':' in slot_key else slot_key
        
        if slot_name not in CANON_SLOTS:
            # Fallback to regular search if slot not found
            return self.search_places(slot_name, limit, offset, user_lat, user_lng, radius_m, "relevance", area)
        
        slot_config = CANON_SLOTS[slot_name]
        include_tags = slot_config.get('include_tags', [])
        include_categories = slot_config.get('include_categories', [])
        exclude_categories = slot_config.get('exclude_categories', [])
        
        # Build search query with tags
        search_query = slot_name
        if include_tags:
            # Add tags to boost relevance
            search_query += " " + " ".join([tag.split(':', 1)[-1] for tag in include_tags])
        
        # Use PostgreSQL FTS with category filtering
        return self._fts_search_with_categories(
            search_query, include_categories, exclude_categories, limit, offset, user_lat, user_lng, area, radius_m
        )
    
    def _fts_search_with_categories(
        self, 
        query: str, 
        include_categories: List[str],
        exclude_categories: List[str],
        limit: int, 
        offset: int,
        user_lat: Optional[float], 
        user_lng: Optional[float],
        area: Optional[str], 
        radius_m: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """FTS search with category filtering"""
        tsq = query.strip()
        where_area = ""
        where_bbox = ""
        where_categories = ""
        
        params = {'tsq': tsq, 'limit': limit, 'offset': offset}
        
        # Add category filtering
        category_conditions = []
        
        # Include categories (OR logic)
        if include_categories:
            include_conditions = []
            for i, cat in enumerate(include_categories):
                param_key = f"inc_cat_{i}"
                include_conditions.append(f"category ILIKE :{param_key}")
                params[param_key] = f"%{cat}%"
            if include_conditions:
                category_conditions.append("(" + " OR ".join(include_conditions) + ")")
        
        # Exclude categories (AND NOT logic)
        if exclude_categories:
            for i, cat in enumerate(exclude_categories):
                param_key = f"exc_cat_{i}"
                category_conditions.append(f"category NOT ILIKE :{param_key}")
                params[param_key] = f"%{cat}%"
        
        if category_conditions:
            where_categories = " AND " + " AND ".join(category_conditions) + " "
        
        # Add area filtering
        if area and area.strip():
            where_area = " AND (tags_csv ILIKE :area OR name ILIKE :area OR summary ILIKE :area) "
            params['area'] = f"%{area.strip()}%"
            
        # Add BBOX prefilter
        if (user_lat is not None) and (user_lng is not None) and (radius_m is not None) and (radius_m > 0):
            lat_min, lat_max, lng_min, lng_max = self._get_geo_bbox(user_lat, user_lng, radius_m)
            where_bbox = " AND lat BETWEEN :lat_min AND :lat_max AND lng BETWEEN :lng_min AND :lng_max "
            params.update({'lat_min': lat_min, 'lat_max': lat_max, 'lng_min': lng_min, 'lng_max': lng_max})
            
        sql = text(f"""
            SELECT id, name, category, summary, tags_csv, lat, lng,
                   picture_url, gmaps_place_id, gmaps_url, rating, processing_status,
                   ts_rank(search_vector, websearch_to_tsquery('simple', :tsq)) AS rank,
                   signals
            FROM epx.places_search_mv
            WHERE processing_status IN ('summarized','published')
              AND search_vector @@ websearch_to_tsquery('simple', :tsq)
              {where_categories}
              {where_area}
              {where_bbox}
            ORDER BY rank DESC NULLS LAST
            LIMIT :limit OFFSET :offset
        """)
        
        rows = self.db.execute(sql, params).fetchall()
        
        def _dist_m(lat1, lng1, lat2, lng2):
            if (lat1 is None) or (lng1 is None) or (lat2 is None) or (lng2 is None):
                return None
            import math
            R = 6371000.0
            la1, lo1, la2, lo2 = map(math.radians, [lat1, lng1, lat2, lng2])
            d = 2*math.asin(math.sqrt(math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2))
            return int(R*d)
            
        out = []
        for r in rows:
            dist_m = _dist_m(user_lat, user_lng, r.lat, r.lng) if (user_lat is not None and user_lng is not None) else None
            out.append({
                "id": r.id, "name": r.name, "summary": r.summary or "", "tags_csv": r.tags_csv or "",
                "category": r.category or "", "lat": r.lat, "lng": r.lng, "picture_url": r.picture_url,
                "gmaps_place_id": r.gmaps_place_id, "gmaps_url": r.gmaps_url, "rating": r.rating, 
                "processing_status": r.processing_status,
                "search_score": float(getattr(r, "rank", 0.0)) * 1000.0,  # нормируем в шкалу 0..1000
                "rank": float(getattr(r, "rank", 0.0)),  # для схемы SearchResult
                "distance_m": dist_m,
                "signals": dict(r.signals) if r.signals else {}
            })
            
        return out
    
    def search_places(
        self, 
        query: Optional[str] = None, 
        limit: int = 20, 
        offset: int = 0,
        user_lat: Optional[float] = None,
        user_lng: Optional[float] = None,
        radius_m: Optional[int] = None,
        sort: str = "relevance",
        area: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Netflix-style smart search with intelligent ranking"""
        
        # Handle empty query - return recent places
        if not query or query.strip() == "":
            return self._get_recent_places(limit, offset, user_lat, user_lng, radius_m, sort)
        
        # дефолт радиуса (10 км), если есть гео, но радиус не указан
        if (radius_m is None) and (user_lat is not None) and (user_lng is not None):
            radius_m = 10000
        
        # Check cache first (LRU)
        cache_key = self._get_cache_key(query, user_lat, user_lng, radius_m, limit, offset, area, sort)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        
        # Используем только FTS (Postgres MV)
        try:
            fts = self._fts_search_pg(query, limit, offset, user_lat, user_lng, area, radius_m)
            if fts:
                # Если нужен строгий радиус — дополнительно отфильтровать
                if (user_lat is not None) and (user_lng is not None) and (radius_m is not None):
                    fts = [p for p in fts if p.get("distance_m") is not None and p["distance_m"] <= radius_m]
                self._cache_set(cache_key, fts)
                return fts
            else:
                # Если FTS пустой, возвращаем пустой результат
                self._cache_set(cache_key, [])
                return []
        except Exception as e:
            logger.error(f"FTS search failed: {e}")
            # В случае ошибки возвращаем пустой результат
            self._cache_set(cache_key, [])
            return []

    # --- NEW: PG FTS over MV ---
    def _fts_search_pg(self, query: str, limit: int, offset: int,
                       user_lat: Optional[float], user_lng: Optional[float],
                       area: Optional[str], radius_m: Optional[int] = None) -> List[Dict[str, Any]]:
        tsq = query.strip()
        where_area = ""
        where_bbox = ""
        params = {'tsq': tsq, 'limit': limit, 'offset': offset}
        if area and area.strip():
            where_area = " AND (tags_csv ILIKE :area OR name ILIKE :area OR summary ILIKE :area) "
            params['area'] = f"%{area.strip()}%"
        # BBOX prefilter при наличии гео и радиуса
        if (user_lat is not None) and (user_lng is not None) and (radius_m is not None) and (radius_m > 0):
            lat_min, lat_max, lng_min, lng_max = self._get_geo_bbox(user_lat, user_lng, radius_m)
            where_bbox = " AND lat BETWEEN :lat_min AND :lat_max AND lng BETWEEN :lng_min AND :lng_max "
            params.update({'lat_min': lat_min, 'lat_max': lat_max, 'lng_min': lng_min, 'lng_max': lng_max})
        sql = text(f"""
            SELECT id, name, category, summary, tags_csv, lat, lng,
                   picture_url, gmaps_place_id, gmaps_url, rating, processing_status,
                   ts_rank(search_vector, websearch_to_tsquery('simple', :tsq)) AS rank,
                   signals
            FROM epx.places_search_mv
            WHERE processing_status IN ('summarized','published')
              AND search_vector @@ websearch_to_tsquery('simple', :tsq)
              {where_area}
              {where_bbox}
            ORDER BY rank DESC NULLS LAST
            LIMIT :limit OFFSET :offset
        """)
        rows = self.db.execute(sql, params).fetchall()
        def _dist_m(lat1, lng1, lat2, lng2):
            if (lat1 is None) or (lng1 is None) or (lat2 is None) or (lng2 is None):
                return None
            import math
            R = 6371000.0
            la1, lo1, la2, lo2 = map(math.radians, [lat1, lng1, lat2, lng2])
            d = 2*math.asin(math.sqrt(math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2))
            return int(R*d)
        out = []
        for r in rows:
            dist_m = _dist_m(user_lat, user_lng, r.lat, r.lng) if (user_lat is not None and user_lng is not None) else None
            out.append({
                "id": r.id, "name": r.name, "summary": r.summary or "", "tags_csv": r.tags_csv or "",
                "category": r.category or "", "lat": r.lat, "lng": r.lng, "picture_url": r.picture_url,
                "gmaps_place_id": r.gmaps_place_id, "gmaps_url": r.gmaps_url, "rating": r.rating, 
                "processing_status": r.processing_status,
                "search_score": float(getattr(r, "rank", 0.0)) * 1000.0,  # нормируем в шкалу 0..1000
                "rank": float(getattr(r, "rank", 0.0)),  # для схемы SearchResult
                "signals": r.signals, "distance_m": dist_m
            })
        return out
    def get_search_suggestions(self, query: str, limit: int = 10) -> List[str]:
        """Get search suggestions based on partial query (Postgres MV)"""
        if not query or len(query.strip()) < 2:
            return []
        tsq = self._build_tsquery(query)
        # websearch_to_tsquery даёт хороший UX для свободного текста
        sql = text("""
            SELECT DISTINCT ON (name) name, tags_csv
            FROM epx.places_search_mv
            WHERE processing_status IN ('summarized','published')
              AND search_vector @@ websearch_to_tsquery('simple', :tsq)
            ORDER BY name ASC
            LIMIT :limit
        """)
        result = self.db.execute(sql, {'tsq': tsq, 'limit': limit})
        suggestions = set()
        for row in result:
            if row.name:
                suggestions.add(row.name)
            if row.tags_csv:
                tags = [tag.strip() for tag in row.tags_csv.split(',') if tag.strip()]
                for tag in tags:
                    if len(tag) >= 2:
                        suggestions.add(tag)
        return list(suggestions)[:limit]
    
    def get_place_count(self, query: Optional[str] = None) -> int:
        """Get total count of matching places (Postgres MV)"""
        if not query or query.strip() == "":
            # Count all published places
            return self.db.query(Place).filter(
                Place.processing_status.in_(['published', 'summarized', 'new'])
            ).count()
        tsq = self._build_tsquery(query)
        sql = text("""
            SELECT COUNT(*) AS count
            FROM epx.places_search_mv
            WHERE processing_status IN ('summarized','published')
              AND search_vector @@ websearch_to_tsquery('simple', :tsq)
        """)
        return int(self.db.execute(sql, {'tsq': tsq}).scalar() or 0)
    
    def clear_cache(self):
        """Clear search cache"""
        self._search_cache.clear()
        logger.info("Search cache cleared")
    
    def search_by_slot(self, slot: Slot, limit: int = 50, offset: int = 0, 
                      user_lat: Optional[float] = None, user_lng: Optional[float] = None,
                      radius_m: Optional[int] = None, area: Optional[str] = None) -> List[Dict[str, Any]]:
        """Поиск мест по слоту с учетом типа слота."""
        logger.debug(f"Searching by slot: {slot.type}:{slot.canonical} (confidence: {slot.confidence:.2f})")
        
        try:
            if slot.type == SlotType.VIBE:
                return self._search_by_vibe_slot(slot, limit, offset, user_lat, user_lng, radius_m, area)
            elif slot.type == SlotType.DISH:
                return self._search_by_dish_slot(slot, limit, offset, user_lat, user_lng, radius_m, area)
            elif slot.type == SlotType.EXPERIENCE:
                return self._search_by_experience_slot(slot, limit, offset, user_lat, user_lng, radius_m, area)
            elif slot.type == SlotType.AREA:
                return self._search_by_area_slot(slot, limit, offset, user_lat, user_lng, radius_m, area)
            elif slot.type == SlotType.CUISINE:
                return self._search_by_cuisine_slot(slot, limit, offset, user_lat, user_lng, radius_m, area)
            elif slot.type == SlotType.DRINK:
                return self._search_by_drink_slot(slot, limit, offset, user_lat, user_lng, radius_m, area)
            else:
                logger.warning(f"Unknown slot type: {slot.type}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to search by slot {slot.type}:{slot.canonical}: {e}")
            return []
    
    def _search_by_vibe_slot(self, slot: Slot, limit: int, offset: int, 
                           user_lat: Optional[float], user_lng: Optional[float],
                           radius_m: Optional[int], area: Optional[str]) -> List[Dict[str, Any]]:
        """Поиск по vibe слотам с учётом rail_policy (include/exclude) и мягких сигналов."""
        import os, yaml
        # 1) Загружаем rail_policy (fail-open)
        include_any_tags: List[str] = []
        exclude_for_vibe_if_dish: List[str] = []
        try:
            path = os.path.join(os.getcwd(), "config", "rail_policy.yml")
            if os.path.exists(path):
                cfg = yaml.safe_load(open(path, "r", encoding="utf-8")) or {}
                rp = ((cfg.get("rail_policy") or {}).get("vibe") or {}).get(slot.canonical, {})
                include_any_tags = rp.get("include_any_tags", []) or []
                # глобальное исключение при наличии dish-слота
                gl = (cfg.get("globals") or {}).get("if_query_has_dish", {})
                exclude_for_vibe_if_dish = gl.get("exclude_for_vibe", []) or []
        except Exception:
            pass

        # 2) Собираем запрос по include_any_tags (OR)
        query_parts = []
        for tag in include_any_tags:
            query_parts.append(f'"{tag}"')
        if not query_parts:
            query_parts = [f'"{slot.canonical}"']
        query = ' OR '.join(query_parts)

        # 3) Выполняем широкий поиск кандидатов
        candidates = self.search_places(
            query=query,
            limit=max(100, limit * 4),
            offset=0,
            user_lat=user_lat,
            user_lng=user_lng,
            radius_m=radius_m or 8000,
            area=area,
            sort="relevance"
        )

        # 4) Если в контексте есть блюдо — исключаем рестораны/кухни (кроме whitelist в compose)
        has_dish = bool(getattr(slot, "context", {}).get("has_dish"))
        if has_dish and exclude_for_vibe_if_dish:
            def _excluded(row: Dict[str, Any]) -> bool:
                tags = (row.get("tags_csv") or "").lower()
                name = (row.get("name") or "").lower()
                for ex in exclude_for_vibe_if_dish:
                    if ex.endswith(":*"):
                        prefix = ex[:-1].lower()
                        if prefix in tags:
                            return True
                    else:
                        if ex.lower() in tags or ex.lower() in name:
                            return True
                return False
            candidates = [c for c in candidates if not _excluded(c)]

        # 5) Возвращаем top N после мягкой фильтрации (детальная ранжировка дальше в compose)
        return candidates[:limit]
    
    def _search_by_dish_slot(self, slot: Slot, limit: int, offset: int,
                            user_lat: Optional[float], user_lng: Optional[float],
                            radius_m: Optional[int], area: Optional[str]) -> List[Dict[str, Any]]:
        """Поиск по dish слотам с мостом dish → cuisine."""
        expands_to_tags = slot.filters.get('expands_to_tags', [])
        
        # Строим запрос
        query_parts = []
        for tag in expands_to_tags:
            if tag.startswith('dish:'):
                query_parts.append(f'"{tag}"')
            elif tag.startswith('cuisine:'):
                # Мост dish → cuisine
                query_parts.append(f'"{tag}"')
        
        # Добавляем текстовый поиск по названию блюда
        query_parts.append(f'"{slot.canonical}"')
        
        query = ' OR '.join(query_parts)
        
        return self.search_places(
            query=query,
            limit=limit,
            offset=offset,
            user_lat=user_lat,
            user_lng=user_lng,
            radius_m=radius_m,
            area=area,
            sort="relevance"
        )
    
    def _search_by_experience_slot(self, slot: Slot, limit: int, offset: int,
                                 user_lat: Optional[float], user_lng: Optional[float],
                                 radius_m: Optional[int], area: Optional[str]) -> List[Dict[str, Any]]:
        """Поиск по experience слотам с подсигналами."""
        expands_to_tags = slot.filters.get('expands_to_tags', [])
        
        query_parts = []
        for tag in expands_to_tags:
            if tag.startswith('experience:'):
                query_parts.append(f'"{tag}"')
            elif tag.startswith('view:'):
                # Подсигнал для view
                query_parts.append(f'"{tag}"')
            elif tag.startswith('scenario:'):
                # Подсигнал для dateworthy
                query_parts.append(f'"{tag}"')
        
        # Добавляем текстовый поиск
        query_parts.append(f'"{slot.canonical}"')
        
        query = ' OR '.join(query_parts)
        
        return self.search_places(
            query=query,
            limit=limit,
            offset=offset,
            user_lat=user_lat,
            user_lng=user_lng,
            radius_m=radius_m,
            area=area,
            sort="relevance"
        )
    
    def _search_by_area_slot(self, slot: Slot, limit: int, offset: int,
                           user_lat: Optional[float], user_lng: Optional[float],
                           radius_m: Optional[int], area: Optional[str]) -> List[Dict[str, Any]]:
        """Поиск по area слотам с геолокацией."""
        expands_to_tags = slot.filters.get('expands_to_tags', [])
        
        query_parts = []
        for tag in expands_to_tags:
            if tag.startswith('area:'):
                query_parts.append(f'"{tag}"')
        
        # Добавляем текстовый поиск по названию района
        query_parts.append(f'"{slot.canonical}"')
        
        query = ' OR '.join(query_parts)
        
        # Используем area параметр если он передан
        search_area = area or slot.canonical
        
        return self.search_places(
            query=query,
            limit=limit,
            offset=offset,
            user_lat=user_lat,
            user_lng=user_lng,
            radius_m=radius_m,
            area=search_area,
            sort="relevance"
        )
    
    def _search_by_cuisine_slot(self, slot: Slot, limit: int, offset: int,
                              user_lat: Optional[float], user_lng: Optional[float],
                              radius_m: Optional[int], area: Optional[str]) -> List[Dict[str, Any]]:
        """Поиск по cuisine слотам."""
        expands_to_tags = slot.filters.get('expands_to_tags', [])
        
        query_parts = []
        for tag in expands_to_tags:
            if tag.startswith('cuisine:'):
                query_parts.append(f'"{tag}"')
        
        # Добавляем текстовый поиск
        query_parts.append(f'"{slot.canonical}"')
        
        query = ' OR '.join(query_parts)
        
        return self.search_places(
            query=query,
            limit=limit,
            offset=offset,
            user_lat=user_lat,
            user_lng=user_lng,
            radius_m=radius_m,
            area=area,
            sort="relevance"
        )
    
    def _search_by_drink_slot(self, slot: Slot, limit: int, offset: int,
                            user_lat: Optional[float], user_lng: Optional[float],
                            radius_m: Optional[int], area: Optional[str]) -> List[Dict[str, Any]]:
        """Поиск по drink слотам."""
        expands_to_tags = slot.filters.get('expands_to_tags', [])
        
        # Используем только текстовый поиск для drink слотов
        query = slot.canonical
        
        # Используем FTS поиск для drink слотов
        return self.search_places(
            query=query,
            limit=limit,
            offset=offset,
            user_lat=user_lat,
            user_lng=user_lng,
            radius_m=radius_m,
            area=area,
            sort="relevance"
        )
    
    def search_by_slots_fallback(self, limit: int = 50, offset: int = 0,
                                user_lat: Optional[float] = None, user_lng: Optional[float] = None,
                                radius_m: Optional[int] = None, area: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fallback поиск на signals.extraordinary/hq_experience."""
        logger.debug("Using fallback search for signals.extraordinary/hq_experience")
        
        # Поиск по extraordinary signals
        query = 'signals.extraordinary:true OR signals.hq_experience:true'
        
        return self.search_places(
            query=query,
            limit=limit,
            offset=offset,
            user_lat=user_lat,
            user_lng=user_lng,
            radius_m=radius_m,
            area=area,
            sort="relevance"
        )


def create_search_service(db: Session) -> SearchService:
    """Factory function to create SearchService instance"""
    return SearchService(db)
