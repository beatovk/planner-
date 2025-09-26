#!/usr/bin/env python3
"""Simple search service for places_search table"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from apps.places.models import Place

logger = logging.getLogger(__name__)


class SimpleSearchService:
    """Simple search service using places_search table"""
    
    def __init__(self, db: Session):
        self.db = db
    
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
        """Search places using simple ILIKE queries"""
        
        # Handle empty query - return recent places
        if not query or query.strip() == "":
            return self._get_recent_places(limit, offset, user_lat, user_lng, radius_m, sort)
        
        # Build search conditions
        conditions = []
        params = {'limit': limit, 'offset': offset}
        
        # Add search query conditions
        if query and query.strip():
            search_term = f"%{query.strip()}%"
            conditions.append("""
                (name ILIKE :search_term OR 
                 tags_csv ILIKE :search_term OR 
                 summary ILIKE :search_term OR 
                 category ILIKE :search_term OR
                 search_text ILIKE :search_term)
            """)
            params['search_term'] = search_term
        
        # Add status filter
        conditions.append("processing_status = 'published'")
        
        # Add area filter
        if area and area.strip():
            conditions.append("(tags_csv ILIKE :area OR name ILIKE :area OR summary ILIKE :area)")
            params['area'] = f"%{area.strip()}%"
        
        # Add geo filter
        if (user_lat is not None) and (user_lng is not None) and (radius_m is not None) and (radius_m > 0):
            # Simple bounding box filter
            lat_delta = radius_m / 111000.0  # Approximate degrees per meter
            lng_delta = radius_m / (111000.0 * abs(user_lat) * 0.017453292519943295)  # Adjust for latitude
            
            conditions.append("""
                lat BETWEEN :lat_min AND :lat_max AND 
                lng BETWEEN :lng_min AND :lng_max
            """)
            params.update({
                'lat_min': user_lat - lat_delta,
                'lat_max': user_lat + lat_delta,
                'lng_min': user_lng - lng_delta,
                'lng_max': user_lng + lng_delta
            })
        
        # Build SQL query
        where_clause = " AND ".join(conditions)
        
        # Add sorting
        order_clause = "created_at DESC"
        if sort == "distance" and user_lat and user_lng:
            # Simple distance sorting (not precise but fast)
            order_clause = f"ABS(lat - {user_lat}) + ABS(lng - {user_lng}) ASC"
        
        sql = text(f"""
            SELECT id, place_id, name, category, summary, tags_csv, lat, lng,
                   picture_url, processing_status, search_text, created_at
            FROM places_search
            WHERE {where_clause}
            ORDER BY {order_clause}
            LIMIT :limit OFFSET :offset
        """)
        
        try:
            rows = self.db.execute(sql, params).fetchall()
            results = []
            
            for row in rows:
                place_dict = {
                    'id': row.place_id,  # Use original place ID
                    'name': row.name,
                    'category': row.category,
                    'summary': row.summary or "",
                    'tags_csv': row.tags_csv or "",
                    'lat': row.lat,
                    'lng': row.lng,
                    'picture_url': row.picture_url,
                    'processing_status': row.processing_status,
                    'search_score': 100,  # Simple score
                    'rank': 1.0,
                    'distance_m': None,
                    'signals': {},
                    # Add required fields for Pydantic validation
                    'gmaps_place_id': None,
                    'gmaps_url': None,
                    'rating': None
                }
                
                # Calculate distance if geo coordinates provided
                if (user_lat is not None and user_lng is not None and 
                    row.lat is not None and row.lng is not None):
                    distance = self._haversine_m(user_lat, user_lng, row.lat, row.lng)
                    place_dict['distance_m'] = int(distance)
                    place_dict['walk_time_min'] = int(distance / 80)  # 80 m/min walking speed
                
                results.append(place_dict)
            
            return results
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
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
        
        conditions = ["processing_status = 'published'"]
        params = {'limit': limit, 'offset': offset}
        
        # Add geo filter
        if (user_lat is not None) and (user_lng is not None) and (radius_m is not None) and (radius_m > 0):
            lat_delta = radius_m / 111000.0
            lng_delta = radius_m / (111000.0 * abs(user_lat) * 0.017453292519943295)
            
            conditions.append("""
                lat BETWEEN :lat_min AND :lat_max AND 
                lng BETWEEN :lng_min AND :lng_max
            """)
            params.update({
                'lat_min': user_lat - lat_delta,
                'lat_max': user_lat + lat_delta,
                'lng_min': user_lng - lng_delta,
                'lng_max': user_lng + lng_delta
            })
        
        where_clause = " AND ".join(conditions)
        order_clause = "created_at DESC"
        
        if sort == "distance" and user_lat and user_lng:
            order_clause = f"ABS(lat - {user_lat}) + ABS(lng - {user_lng}) ASC"
        
        sql = text(f"""
            SELECT id, place_id, name, category, summary, tags_csv, lat, lng,
                   picture_url, processing_status, search_text, created_at
            FROM places_search
            WHERE {where_clause}
            ORDER BY {order_clause}
            LIMIT :limit OFFSET :offset
        """)
        
        try:
            rows = self.db.execute(sql, params).fetchall()
            results = []
            
            for row in rows:
                place_dict = {
                    'id': row.place_id,
                    'name': row.name,
                    'category': row.category,
                    'summary': row.summary or "",
                    'tags_csv': row.tags_csv or "",
                    'lat': row.lat,
                    'lng': row.lng,
                    'picture_url': row.picture_url,
                    'processing_status': row.processing_status,
                    'search_score': 100,
                    'rank': 1.0,
                    'distance_m': None,
                    'signals': {},
                    # Add required fields for Pydantic validation
                    'gmaps_place_id': None,
                    'gmaps_url': None,
                    'rating': None
                }
                
                if (user_lat is not None and user_lng is not None and 
                    row.lat is not None and row.lng is not None):
                    distance = self._haversine_m(user_lat, user_lng, row.lat, row.lng)
                    place_dict['distance_m'] = int(distance)
                    place_dict['walk_time_min'] = int(distance / 80)
                
                results.append(place_dict)
            
            return results
            
        except Exception as e:
            logger.error(f"Recent places error: {e}")
            return []
    
    def get_place_count(self, query: Optional[str] = None) -> int:
        """Get total count of matching places"""
        if not query or query.strip() == "":
            # Count all published places
            sql = text("SELECT COUNT(*) FROM places_search WHERE processing_status = 'published'")
            return int(self.db.execute(sql).scalar() or 0)
        
        search_term = f"%{query.strip()}%"
        sql = text("""
            SELECT COUNT(*) FROM places_search
            WHERE processing_status = 'published'
              AND (name ILIKE :search_term OR 
                   tags_csv ILIKE :search_term OR 
                   summary ILIKE :search_term OR 
                   category ILIKE :search_term OR
                   search_text ILIKE :search_term)
        """)
        return int(self.db.execute(sql, {'search_term': search_term}).scalar() or 0)
    
    def get_search_suggestions(self, query: str, limit: int = 10) -> List[str]:
        """Get search suggestions based on partial query"""
        if not query or len(query.strip()) < 2:
            return []
        
        search_term = f"%{query.strip()}%"
        sql = text("""
            SELECT DISTINCT name, tags_csv
            FROM places_search
            WHERE processing_status = 'published'
              AND (name ILIKE :search_term OR tags_csv ILIKE :search_term)
            ORDER BY name ASC
            LIMIT :limit
        """)
        
        try:
            result = self.db.execute(sql, {'search_term': search_term, 'limit': limit})
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
            
        except Exception as e:
            logger.error(f"Suggestions error: {e}")
            return []
    
    def _haversine_m(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate distance between two points in meters"""
        import math
        R = 6371000.0  # Earth radius in meters
        la1, lo1, la2, lo2 = map(math.radians, [lat1, lng1, lat2, lng2])
        d = 2 * math.asin(math.sqrt(
            math.sin((la2 - la1) / 2) ** 2 + 
            math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
        ))
        return R * d


def create_simple_search_service(db: Session) -> SimpleSearchService:
    """Factory function to create SimpleSearchService instance"""
    return SimpleSearchService(db)
