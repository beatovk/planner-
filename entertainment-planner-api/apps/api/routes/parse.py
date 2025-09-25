#!/usr/bin/env python3
"""Parse API for Netflix-style search system"""

import time
import hashlib
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.core.db import get_db
from apps.places.schemas.vibes import ParseRequest, ParseResult
from apps.places.services.heuristic_parser import create_heuristic_parser, load_ontology

logger = logging.getLogger(__name__)

router = APIRouter()

# Global cache for parse results
_parse_cache: Dict[str, Dict[str, Any]] = {}
_cache_ttl = 15 * 60  # 15 minutes in seconds


def get_cache_key(request: ParseRequest) -> str:
    """Generate cache key for parse request"""
    # Normalize query for consistent caching
    query_normalized = request.query.lower().strip()
    
    # Create hash of normalized parameters
    params = {
        'query': query_normalized,
        'area': request.area,
        'user_lat': round(request.user_lat, 4) if (request.user_lat is not None) else None,
        'user_lng': round(request.user_lng, 4) if (request.user_lng is not None) else None
    }
    
    params_str = str(sorted(params.items()))
    return hashlib.md5(params_str.encode()).hexdigest()


def is_cache_valid(cache_entry: Dict[str, Any]) -> bool:
    """Check if cache entry is still valid"""
    return time.time() - cache_entry['timestamp'] < _cache_ttl


def get_cached_result(cache_key: str) -> Optional[ParseResult]:
    """Get cached parse result if valid"""
    if cache_key in _parse_cache:
        cache_entry = _parse_cache[cache_key]
        if is_cache_valid(cache_entry):
            logger.debug(f"Cache hit for key: {cache_key}")
            return ParseResult.model_validate(cache_entry['result'])
        else:
            # Remove expired entry
            del _parse_cache[cache_key]
            logger.debug(f"Cache expired for key: {cache_key}")
    
    return None


def cache_result(cache_key: str, result: ParseResult):
    """Cache parse result"""
    _parse_cache[cache_key] = {
        'result': result.model_dump(),
        'timestamp': time.time()
    }
    
    # Clean up old entries if cache is too large
    if len(_parse_cache) > 1000:  # Max 1000 entries
        # Remove oldest 20% of entries
        sorted_entries = sorted(_parse_cache.items(), key=lambda x: x[1]['timestamp'])
        entries_to_remove = len(sorted_entries) // 5
        for key, _ in sorted_entries[:entries_to_remove]:
            del _parse_cache[key]
        
        logger.info(f"Cleaned up cache, removed {entries_to_remove} entries")


@router.post("/parse", response_model=ParseResult)
async def parse_query(
    request: ParseRequest,
    db: Session = Depends(get_db)
):
    """
    Parse user query into structured format with vibes, scenarios, and experiences.
    
    This endpoint uses heuristic parsing with dynamic confidence thresholds:
    - Vague queries ("something interesting") → confidence threshold 0.4
    - Structured queries ("tom yum, spa, rooftop") → confidence threshold 0.7
    
    Results are cached for 15 minutes to improve performance.
    """
    start_time = time.time()
    
    try:
        # Check cache first
        cache_key = get_cache_key(request)
        cached_result = get_cached_result(cache_key)
        
        if cached_result:
            # Add cache hit info
            cached_result.cache_hit = True
            cached_result.processing_time_ms = (time.time() - start_time) * 1000
            return cached_result
        
        # Load ontology and create parser
        ontology = load_ontology()
        parser = create_heuristic_parser()
        
        # Parse query
        result = parser.parse(request)
        
        # Add processing time
        result.processing_time_ms = (time.time() - start_time) * 1000
        result.cache_hit = False
        
        # Cache result
        cache_result(cache_key, result)
        
        logger.info(f"Parsed query '{request.query[:50]}...' in {result.processing_time_ms:.2f}ms, confidence: {result.confidence:.2f}")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to parse query '{request.query}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse query: {str(e)}")


@router.get("/parse/cache/stats")
async def get_cache_stats():
    """Get cache statistics for monitoring"""
    current_time = time.time()
    
    # Count valid and expired entries
    valid_entries = 0
    expired_entries = 0
    
    for entry in _parse_cache.values():
        if is_cache_valid(entry):
            valid_entries += 1
        else:
            expired_entries += 1
    
    return {
        "total_entries": len(_parse_cache),
        "valid_entries": valid_entries,
        "expired_entries": expired_entries,
        "cache_ttl_seconds": _cache_ttl,
        "cache_ttl_minutes": _cache_ttl / 60
    }


@router.delete("/parse/cache")
async def clear_cache():
    """Clear parse cache"""
    global _parse_cache
    entries_count = len(_parse_cache)
    _parse_cache.clear()
    
    logger.info(f"Cleared parse cache, removed {entries_count} entries")
    
    return {
        "message": f"Cache cleared, removed {entries_count} entries",
        "entries_removed": entries_count
    }


@router.get("/parse/ontology")
async def get_ontology():
    """Get current vibes ontology for debugging"""
    try:
        ontology = load_ontology()
        return {
            "vibes_count": len(ontology.vibes),
            "scenarios_count": len(ontology.scenarios),
            "experiences_count": len(ontology.experiences),
            "food_drink_modifiers_count": len(ontology.food_drink_modifiers),
            "total_tags": len(ontology.get_alias_map()),
            "confidence_thresholds": ontology.parsing.confidence_thresholds
        }
    except Exception as e:
        logger.error(f"Failed to load ontology: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load ontology: {str(e)}")


@router.post("/parse/test")
async def test_parse(
    query: str = Query(..., description="Test query to parse"),
    area: Optional[str] = Query(None, description="Area filter"),
    user_lat: Optional[float] = Query(None, description="User latitude"),
    user_lng: Optional[float] = Query(None, description="User longitude")
):
    """Test endpoint for parsing queries without caching"""
    try:
        request = ParseRequest(
            query=query,
            area=area,
            user_lat=user_lat,
            user_lng=user_lng
        )
        
        ontology = load_ontology()
        parser = create_heuristic_parser()
        
        result = parser.parse(request)
        
        return {
            "query": query,
            "result": result.model_dump(),
            "ontology_stats": {
                "total_tags": len(ontology.get_alias_map()),
                "confidence_thresholds": ontology.parsing.confidence_thresholds
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to test parse query '{query}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to test parse: {str(e)}")
