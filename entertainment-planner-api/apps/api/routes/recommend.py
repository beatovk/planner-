#!/usr/bin/env python3
"""Route recommendation API endpoints"""

import time
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from apps.core.db import get_db
from apps.places.services.route import RouteService
from apps.places.services.search import create_search_service
from apps.api.schemas.route import RouteRequest, RouteResponse

router = APIRouter(prefix="/api", tags=["recommendations"])


@router.post("/routes", response_model=RouteResponse)
def build_routes(
    request: RouteRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Build entertainment route based on vibe and preferences.
    
    Uses beam search algorithm to find optimal sequence of places
    considering geography, opening hours, and vibe alignment.
    """
    start_time = time.time()
    
    try:
        # Create services
        search_service = create_search_service(db)
        route_service = RouteService(search_service)
        
        # Convert origin to dict if provided
        origin_dict = None
        if request.origin:
            origin_dict = {
                "lat": request.origin.lat,
                "lng": request.origin.lng
            }
        
        # Build route
        result = route_service.build_route(
            vibe=request.vibe,
            steps=request.steps,
            origin=origin_dict,
            radius_m=request.radius_m,
            time_start=request.time_start,
            limit_per_step=request.limit_per_step
        )
        
        # Calculate processing time
        processing_time = round((time.time() - start_time) * 1000, 2)  # ms
        
        # Add debug headers
        response.headers["X-Route-Debug"] = f"intent={result['debug'].get('match_profile', 'unknown')}, took={processing_time}ms"
        response.headers["X-Route-Candidates"] = f"eat={result['debug']['candidates'].get('eat', 0)}, walk={result['debug']['candidates'].get('walk', 0)}, drink={result['debug']['candidates'].get('drink', 0)}"
        
        if result['route'] and 'signals' in result['debug']:
            signals = result['debug']['signals']
            response.headers["X-Route-Signals"] = f"open={signals.get('open_now', 0)}, geo={signals.get('geo', 0)}, bm25={signals.get('bm25', 0)}, vibe={signals.get('vibe', 0)}"
        
        return RouteResponse(**result)
        
    except Exception as e:
        processing_time = round((time.time() - start_time) * 1000, 2)
        response.headers["X-Route-Debug"] = f"error={str(e)[:50]}, took={processing_time}ms"
        raise HTTPException(
            status_code=500,
            detail=f"Error building route: {str(e)}"
        )
