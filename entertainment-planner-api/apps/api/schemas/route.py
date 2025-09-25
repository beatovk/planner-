#!/usr/bin/env python3
"""Pydantic schemas for route planning API"""

import math
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any


class Origin(BaseModel):
    """Origin coordinates"""
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lng: float = Field(..., ge=-180, le=180, description="Longitude")
    
    @validator('lat', 'lng')
    def validate_coordinates(cls, v):
        """Validate coordinates are not NaN or infinite"""
        if math.isnan(v) or math.isinf(v):
            raise ValueError('Coordinates must be valid numbers, not NaN or infinite')
        return v


class Place(BaseModel):
    """Place information in route step"""
    id: int
    name: str
    lat: float
    lng: float
    summary: Optional[str] = None
    category: Optional[str] = None
    address: Optional[str] = None
    
    @validator('lat', 'lng')
    def validate_coordinates(cls, v):
        """Validate coordinates are not NaN or infinite"""
        if math.isnan(v) or math.isinf(v):
            raise ValueError('Coordinates must be valid numbers, not NaN or infinite')
        return v


class RouteStep(BaseModel):
    """Single step in a route"""
    intent: str = Field(..., description="Step intent (eat, walk, drink)")
    place: Place
    walk_dist_m: int = Field(..., description="Walking distance in meters")
    walk_time_min: int = Field(..., description="Walking time in minutes")
    eta_min: int = Field(..., description="Estimated time at place in minutes")


class Route(BaseModel):
    """Complete route information"""
    steps: List[RouteStep]
    total_distance_m: int = Field(..., description="Total distance in meters")
    total_time_min: int = Field(..., description="Total time in minutes")
    score: float = Field(..., description="Route quality score")


class RouteDebug(BaseModel):
    """Debug information for route"""
    match_profile: str = Field(..., description="Search profile used")
    candidates: Dict[str, int] = Field(..., description="Number of candidates per intent")
    signals: Optional[Dict[str, float]] = Field(None, description="Scoring signals")


class RouteRequest(BaseModel):
    """Request for route planning"""
    vibe: str = Field("", description="Free-text vibe, e.g. 'chill date tom yum rooftop'")
    steps: Optional[List[str]] = Field(
        default=None, 
        description="List of intents (eat, walk, drink). Default: ['eat', 'walk', 'drink']"
    )
    origin: Optional[Origin] = Field(None, description="Starting coordinates")
    radius_m: int = Field(2000, ge=100, le=50000, description="Search radius in meters")
    time_start: Optional[str] = Field(None, description="Start time in ISO format")
    limit_per_step: int = Field(6, ge=1, le=20, description="Candidates per step")


class RouteResponse(BaseModel):
    """Response from route planning"""
    route: Optional[Route] = Field(None, description="Generated route")
    debug: RouteDebug = Field(..., description="Debug information")
