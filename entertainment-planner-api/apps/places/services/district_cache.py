#!/usr/bin/env python3
"""District viewport caching service"""

import time
import logging
from typing import Optional, Dict, Any
from apps.places.services.bangkok_districts import get_district_bounds

logger = logging.getLogger(__name__)

class DistrictViewportCache:
    """In-memory cache for district viewport bounds"""
    
    def __init__(self, ttl_hours: int = 24):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl_seconds = ttl_hours * 3600
    
    def get_viewport(self, district_name: str) -> Optional[Dict[str, float]]:
        """Get viewport bounds for district, with caching"""
        if not district_name:
            return None
        
        # Normalize district name
        district_key = district_name.strip().lower()
        
        # Check cache first
        if district_key in self.cache:
            cached_data = self.cache[district_key]
            if time.time() - cached_data["timestamp"] < self.ttl_seconds:
                logger.info(f"Cache hit for district: {district_name}")
                return cached_data["viewport"]
            else:
                # Cache expired, remove it
                del self.cache[district_key]
                logger.info(f"Cache expired for district: {district_name}")
        
        # Cache miss or expired - get from our mapping
        try:
            district_data = get_district_bounds(district_name)
            if district_data:
                viewport = {
                    "lat_min": district_data["lat_min"],
                    "lat_max": district_data["lat_max"],
                    "lng_min": district_data["lng_min"],
                    "lng_max": district_data["lng_max"]
                }
                # Cache the result
                self.cache[district_key] = {
                    "viewport": viewport,
                    "timestamp": time.time()
                }
                logger.info(f"Cached viewport for district: {district_name}")
                return viewport
            else:
                logger.warning(f"No viewport found for district: {district_name}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error getting viewport for district {district_name}: {e}")
            return None
    
    def clear_cache(self):
        """Clear all cached viewports"""
        self.cache.clear()
        logger.info("District viewport cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        current_time = time.time()
        active_entries = 0
        expired_entries = 0
        
        for entry in self.cache.values():
            if current_time - entry["timestamp"] < self.ttl_seconds:
                active_entries += 1
            else:
                expired_entries += 1
        
        return {
            "total_entries": len(self.cache),
            "active_entries": active_entries,
            "expired_entries": expired_entries,
            "ttl_hours": self.ttl_seconds / 3600
        }

# Global cache instance
district_cache = DistrictViewportCache()
