import logging
import time
from fastapi import APIRouter, Depends, HTTPException, Query, Response

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session
from apps.core.db import get_db
from apps.places.models import Place
from apps.places.services.search import create_search_service
from apps.api.schemas.place import PlaceResponse, PlaceDetail
from apps.api.schemas.search import (
    SearchRequest, 
    SearchResponse, 
    SearchSuggestionsRequest, 
    SearchSuggestionsResponse
)
from typing import List, Optional

router = APIRouter()


@router.get("/places", response_model=List[PlaceResponse])
async def get_places(
    skip: int = 0,
    limit: int = 100,
    status: str = None,
    db: Session = Depends(get_db)
):
    """Get list of places with optional filtering by status"""
    query = db.query(Place)
    
    if status:
        query = query.filter(Place.processing_status == status)
    
    places = query.offset(skip).limit(limit).all()
    
    return places


@router.get("/places/search", response_model=SearchResponse)
async def search_places(
    q: Optional[str] = Query(None, min_length=0, max_length=100, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    user_lat: Optional[float] = Query(None, ge=-90, le=90, description="User latitude"),
    user_lng: Optional[float] = Query(None, ge=-180, le=180, description="User longitude"),
    radius_m: Optional[int] = Query(None, ge=100, le=50000, description="Search radius in meters"),
    sort: str = Query("relevance", description="Sort order: relevance or distance"),
    area: Optional[str] = Query(None, description="District/area name for filtering"),
    response: Response = None,
    db: Session = Depends(get_db)
):
    """Search places using FTS5 with BM25 ranking"""
    start_time = time.time()
    
    try:
        # Use smart search service
        search_service = create_search_service(db)
        
        # Get search results using smart search
        results = search_service.search_places(
            query=q,
            limit=limit,
            offset=offset,
            user_lat=user_lat,
            user_lng=user_lng,
            radius_m=radius_m,
            sort=sort,
            area=area
        )
        
        # Get total count
        total_count = search_service.get_place_count(q)
        
        # Check if there are more results
        has_more = (offset + len(results)) < total_count
        
        # Calculate processing time
        processing_time = round((time.time() - start_time) * 1000, 2)  # ms
        
        # Add debug headers
        if response:
            response.headers["X-Search-Debug"] = f"query={q}, took={processing_time}ms, results={len(results)}"
            response.headers["X-Search-Cache"] = f"hits={getattr(search_service, '_cache_hits', 0)}, misses={getattr(search_service, '_cache_misses', 0)}"
        
        return SearchResponse(
            results=results,
            total_count=total_count,
            query=q or "",
            limit=limit,
            offset=offset,
            has_more=has_more
        )
    
    except Exception:
        # Log error and return empty results
        logger.exception("Search error")
        return SearchResponse(
            results=[],
            total_count=0,
            query=q or "",
            limit=limit,
            offset=0,
            has_more=False
        )


@router.get("/places/suggest", response_model=SearchSuggestionsResponse)
async def get_search_suggestions(
    q: str = Query(..., min_length=1, max_length=50, description="Partial search query"),
    limit: int = Query(10, ge=1, le=20, description="Maximum number of suggestions"),
    db: Session = Depends(get_db)
):
    """Get search suggestions based on partial query"""
    search_service = create_search_service(db)
    
    suggestions = search_service.get_search_suggestions(q, limit)
    
    return SearchSuggestionsResponse(
        suggestions=suggestions,
        query=q
    )


@router.get("/places/{place_id}", response_model=PlaceDetail)
async def get_place(place_id: int, db: Session = Depends(get_db)):
    """Get place details by ID"""
    place = db.query(Place).filter(Place.id == place_id).first()
    
    if not place:
        raise HTTPException(status_code=404, detail="Place not found")
    
    return place
