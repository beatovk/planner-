"""Pydantic schemas for search functionality"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class SearchRequest(BaseModel):
    """Request schema for search endpoint"""
    q: Optional[str] = Field(None, min_length=0, max_length=100, description="Search query")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Number of results to skip")
    user_lat: Optional[float] = Field(None, ge=-90, le=90, description="User latitude for geo filtering")
    user_lng: Optional[float] = Field(None, ge=-180, le=180, description="User longitude for geo filtering")
    radius_m: Optional[int] = Field(None, ge=100, le=50000, description="Search radius in meters")


class SearchResult(BaseModel):
    """Individual search result"""
    id: int
    name: str
    category: Optional[str]
    summary: Optional[str]
    tags_csv: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    picture_url: Optional[str]
    gmaps_place_id: Optional[str]
    gmaps_url: Optional[str]
    rating: Optional[float]
    processing_status: str
    rank: float


class SearchResponse(BaseModel):
    """Response schema for search endpoint"""
    results: List[SearchResult]
    total_count: int
    query: str
    limit: int
    offset: int
    has_more: bool


class SearchSuggestionsRequest(BaseModel):
    """Request schema for search suggestions"""
    q: str = Field(..., min_length=1, max_length=50, description="Partial search query")
    limit: int = Field(10, ge=1, le=20, description="Maximum number of suggestions")


class SearchSuggestionsResponse(BaseModel):
    """Response schema for search suggestions"""
    suggestions: List[str]
    query: str
