#!/usr/bin/env python3
"""Pydantic schemas for admin API"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from apps.places.models import PlaceStatus


class AdminPlaceItem(BaseModel):
    """Place item in admin list"""
    id: int
    name: str
    status: str = Field(..., alias="processing_status")
    summary: Optional[str] = None
    tags_csv: Optional[str] = None
    updated_at: datetime
    category: Optional[str] = None
    address: Optional[str] = None
    
    # Теневая схема (Итерация 5)
    attempts: Optional[Dict[str, int]] = None
    quality_flags: Optional[Dict[str, str]] = None
    events_count: Optional[int] = None


class AdminPlacePatch(BaseModel):
    """Request to update place"""
    processing_status: Optional[str] = Field(None, description="New processing status")
    summary: Optional[str] = Field(None, description="Updated summary")
    tags_csv: Optional[str] = Field(None, description="Updated tags")
    
    # Теневая схема (Итерация 5)
    attempts: Optional[Dict[str, int]] = Field(None, description="Update attempts")
    quality_flags: Optional[Dict[str, str]] = Field(None, description="Update quality flags")


class AdminPlaceListResponse(BaseModel):
    """Response for admin place list"""
    total: int = Field(..., description="Total number of places")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    items: List[AdminPlaceItem] = Field(..., description="List of places")


class AdminPlaceUpdateResponse(BaseModel):
    """Response for place update"""
    id: int
    status: str = Field(..., alias="processing_status")
    summary: Optional[str] = None
    tags_csv: Optional[str] = None
