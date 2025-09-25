#!/usr/bin/env python3
"""Route service with beam search algorithm for entertainment planning"""

import math
import datetime as dt
import hashlib
import json
import time
from typing import List, Dict, Any, Optional, Tuple
from zoneinfo import ZoneInfo
from itertools import product

BKK = ZoneInfo("Asia/Bangkok")

# Default durations for different intents (in minutes)
DEFAULT_DUR = {"eat": 75, "walk": 45, "drink": 90}

# City factor for pedestrian walking speed (accounts for traffic lights, blocks)
CITY_FACTOR = 1.25

# Walking speed: 80 m/min = 4.8 km/h
WALKING_SPEED_M_PER_MIN = 80


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two points using Haversine formula"""
    R = 6371000.0  # Earth radius in meters
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dlmb/2)**2
    return 2*R*math.asin(math.sqrt(a))


def to_minutes(time_str: str) -> int:
    """Convert HH:MM to minutes since midnight"""
    h, m = map(int, time_str.split(':'))
    return h * 60 + m


def is_open_now(hours_json: Optional[Dict[str, List[str]]], when: dt.datetime) -> float:
    """
    Check if place is open at given time with support for overnight hours.
    Returns score: 1.0 (open), 0.6 (closing soon), 0.1 (unknown), -0.3 (closed)
    """
    if not hours_json:
        return 0.1  # neutral-positive for unknown hours
    
    day = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][when.weekday()]
    spans = hours_json.get(day) or []
    
    if not spans:
        return 0.1  # neutral for no hours on this day
    
    now_hm = when.strftime("%H:%M")
    n = to_minutes(now_hm)
    
    for span in spans:
        if '-' not in span:
            continue
        start, end = span.split("-")
        a, b = to_minutes(start), to_minutes(end)
        
        if a <= b:
            # Normal range (e.g., 08:00-17:00)
            if a <= n <= b:
                mins_to_close = b - n
                return 1.0 if mins_to_close > 60 else 0.6
        else:
            # Overnight range (e.g., 18:00-02:00)
            if n >= a or n <= b:
                mins_to_close = (b + 24*60 - n) % (24*60)  # handle day rollover
                return 1.0 if mins_to_close > 60 else 0.6
    
    return -0.3  # closed


def vibe_alignment(tags: List[str], user_tokens: List[str]) -> float:
    """Calculate alignment between place tags and user query tokens"""
    if not tags or not user_tokens:
        return 0.0
    
    s1 = set(t.lower() for t in tags)
    s2 = set(t.lower() for t in user_tokens)
    
    if not s1 or not s2:
        return 0.0
    
    intersection = len(s1 & s2)
    return min(1.0, intersection / max(3, len(s2)))


def geo_compactness_score(total_distance: float, radius_m: int, num_steps: int) -> float:
    """Calculate geo compactness score (closer = better)"""
    max_expected_distance = radius_m * num_steps
    return max(0.0, 1.0 - total_distance / max_expected_distance)


def diversity_bonus(places: List[Any]) -> float:
    """Calculate diversity bonus for different categories/areas"""
    if len(places) < 2:
        return 0.0
    
    categories = [getattr(p, 'category', '') for p in places]
    unique_categories = len(set(categories))
    
    # Bonus for different categories
    category_bonus = min(0.5, (unique_categories - 1) * 0.2)
    
    # Penalty for same mall/area (simplified)
    # TODO: Add area detection logic
    
    return category_bonus


class RouteService:
    """Route service with beam search algorithm"""
    
    def __init__(self, search_service):
        self.search_service = search_service
        
        # Intent to tags mapping
        self.intent_tags = {
            "eat": ["restaurant", "cafe", "brunch", "thai", "tom yum", "food", "dining"],
            "walk": ["park", "art", "river", "stroll", "museum", "gallery", "walking"],
            "drink": ["bar", "rooftop", "cocktail", "craft beer", "jazz", "lounge", "pub"]
        }
        
        # Cache for route results (max 50 entries, TTL 10 minutes)
        self._route_cache = {}
        self._cache_ttl = 600  # 10 minutes
    
    def _get_route_cache_key(self, vibe: str, steps: List[str], origin: Optional[Dict[str, float]], 
                           radius_m: int, time_start: Optional[str], limit_per_step: int) -> str:
        """Generate cache key for route parameters"""
        # Round coordinates to reduce cache misses for nearby locations
        origin_key = None
        if origin:
            origin_key = {
                'lat': round(origin['lat'], 4),
                'lng': round(origin['lng'], 4)
            }
        
        # Create hash of route parameters
        params = {
            'vibe': vibe,
            'steps': steps,
            'origin': origin_key,
            'radius_m': radius_m,
            'time_start': time_start,
            'limit_per_step': limit_per_step
        }
        params_str = json.dumps(params, sort_keys=True)
        return hashlib.md5(params_str.encode()).hexdigest()
    
    def _is_route_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if route cache entry is still valid"""
        return time.time() - cache_entry['timestamp'] < self._cache_ttl
    
    def _get_candidates_for_intent(
        self, 
        intent: str, 
        vibe_tokens: List[str], 
        origin: Optional[Dict[str, float]], 
        radius_m: int, 
        limit: int
    ) -> List[Any]:
        """Get candidates for specific intent using search service"""
        # Use simpler query - just vibe tokens for now
        query = " ".join(vibe_tokens) if vibe_tokens else intent
        
        return self.search_service.search_places(
            query=query,
            user_lat=origin.get("lat") if origin else None,
            user_lng=origin.get("lng") if origin else None,
            radius_m=radius_m,
            limit=limit
        )
    
    def _calculate_route_score(
        self, 
        places: List[Any], 
        intents: List[str], 
        vibe_tokens: List[str], 
        origin: Dict[str, float], 
        radius_m: int,
        when: dt.datetime
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """Calculate score for a route and return route details"""
        
        # Check for duplicates
        place_ids = [p.get('id') if isinstance(p, dict) else p.id for p in places]
        if len(place_ids) != len(set(place_ids)):
            return -1000.0, []  # Heavy penalty for duplicates
        
        # Calculate distances and ETA
        total_distance = 0.0
        current_time = when
        prev_location = origin
        route_legs = []
        
        for i, (place, intent) in enumerate(zip(places, intents)):
            # Handle both dict and object formats
            if isinstance(place, dict):
                place_lat = place['lat']
                place_lng = place['lng']
                place_hours = place.get('hours_json')
                place_tags = place.get('tags_csv', '').split(',') if place.get('tags_csv') else []
                place_rank = place.get('rank', 0.0)
            else:
                place_lat = place.lat
                place_lng = place.lng
                place_hours = getattr(place, 'hours_json', None)
                place_tags = place.tags_csv.split(',') if place.tags_csv else []
                place_rank = getattr(place, 'rank', 0.0)
            
            # Calculate distance and walking time
            dist = haversine_m(
                prev_location["lat"], prev_location["lng"],
                place_lat, place_lng
            )
            walk_time_min = max(3, int(dist / WALKING_SPEED_M_PER_MIN * CITY_FACTOR))
            
            # Get duration for this intent
            eta_min = DEFAULT_DUR.get(intent, 60)
            
            # Calculate open now score
            open_score = is_open_now(place_hours, current_time)
            
            # Calculate vibe alignment
            vibe_score = vibe_alignment(place_tags, vibe_tokens)
            
            # Store leg details
            leg = {
                'place': place,
                'intent': intent,
                'distance': dist,
                'walk_time_min': walk_time_min,
                'eta_min': eta_min,
                'open_score': open_score,
                'vibe_score': vibe_score,
                'bm25_rank': place_rank
            }
            route_legs.append(leg)
            
            # Update for next iteration
            total_distance += dist
            current_time += dt.timedelta(minutes=walk_time_min + eta_min)
            prev_location = {"lat": place_lat, "lng": place_lng}
        
        # Calculate final scores
        geo_compact = geo_compactness_score(total_distance, radius_m, len(intents))
        open_avg = sum(leg['open_score'] for leg in route_legs) / len(route_legs)
        vibe_avg = sum(leg['vibe_score'] for leg in route_legs) / len(route_legs)
        bm25_avg = sum(leg['bm25_rank'] for leg in route_legs) / len(route_legs)
        diversity = diversity_bonus(places)
        
        # Final score (higher is better)
        score = (
            1.0 * (-bm25_avg) +      # α: text relevance
            0.7 * geo_compact +      # β: geo compactness  
            0.6 * open_avg +         # γ: open now
            0.5 * vibe_avg +         # δ: vibe alignment
            0.2 * diversity          # ε: diversity bonus
        )
        
        return score, route_legs
    
    def build_route(
        self,
        vibe: str,
        steps: Optional[List[str]] = None,
        origin: Optional[Dict[str, float]] = None,
        radius_m: int = 2000,
        time_start: Optional[str] = None,
        limit_per_step: int = 6,
        beam_width: int = 3
    ) -> Dict[str, Any]:
        """Build route using beam search algorithm - simplified version"""
        
        try:
            # Simple implementation for now
            intents = steps or ["eat", "walk", "drink"]
            
            return {
                "route": {
                    "steps": [],
                    "total_distance_m": 0,
                    "total_time_min": 0,
                    "score": 0.0
                },
                "debug": {
                    "match_profile": "simplified",
                    "candidates": {},
                    "signals": {}
                }
            }
        except Exception as e:
            return {
                "route": None,
                "debug": {
                    "match_profile": "error",
                    "error": str(e)
                }
            }
