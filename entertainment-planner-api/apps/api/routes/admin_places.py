#!/usr/bin/env python3
"""Admin API endpoints for place moderation"""

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from apps.core.db import get_db
from apps.core.config import settings
from apps.places.models import Place, PlaceStatus, PlaceEvent
from apps.places.shadow_utils import ShadowAttemptsManager, ShadowQualityManager
import json
from apps.api.schemas.admin import (
    AdminPlaceListResponse, 
    AdminPlacePatch, 
    AdminPlaceUpdateResponse
)
from typing import Optional

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(x_admin_token: str = Header(None)):
    """Require admin authentication"""
    if not x_admin_token or x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


@router.get("/places", response_model=AdminPlaceListResponse)
def list_places(
    status: Optional[str] = Query(None, description="Filter by processing status"),
    q: Optional[str] = Query(None, description="Search query"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin)
):
    """List places with filtering and pagination"""
    
    # Build query
    query = db.query(Place)
    
    # Apply status filter (поддержка новых статусов)
    if status:
        # Проверяем, является ли статус новым
        if status in [s.value for s in PlaceStatus]:
            query = query.filter(Place.processing_status == status)
        else:
            # Старые статусы для обратной совместимости
            query = query.filter(Place.processing_status == status)
    
    # Apply search filter
    if q:
        # Simple LIKE search for MVP
        search_filter = or_(
            Place.name.ilike(f"%{q}%"),
            Place.summary.ilike(f"%{q}%"),
            Place.tags_csv.ilike(f"%{q}%")
        )
        query = query.filter(search_filter)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * per_page
    items = query.order_by(Place.updated_at.desc()).offset(offset).limit(per_page).all()
    
    # Convert to response format (с поддержкой теневой схемы)
    place_items = []
    for place in items:
        # Получаем теневые данные
        attempts = ShadowAttemptsManager.get_attempts(place)
        quality_flags = ShadowQualityManager.get_quality_flags(place)
        
        # Считаем события
        events_count = db.query(PlaceEvent).filter(PlaceEvent.place_id == place.id).count()
        
        place_items.append(AdminPlaceItem(
            id=place.id,
            name=place.name,
            processing_status=place.processing_status,
            summary=place.summary,
            tags_csv=place.tags_csv,
            updated_at=place.updated_at,
            category=place.category,
            address=place.address,
            # Теневая схема
            attempts=attempts,
            quality_flags=quality_flags,
            events_count=events_count
        ))
    
    return AdminPlaceListResponse(
        total=total,
        page=page,
        per_page=per_page,
        items=place_items
    )


@router.patch("/places/{place_id}", response_model=AdminPlaceUpdateResponse)
def patch_place(
    place_id: int,
    body: AdminPlacePatch,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin)
):
    """Update place status and content"""
    
    # Find place
    place = db.query(Place).get(place_id)
    if not place:
        raise HTTPException(status_code=404, detail="Place not found")
    
    # Update fields (с поддержкой новых статусов)
    if body.processing_status is not None:
        # Validate status (новые + старые статусы)
        valid_statuses = [s.value for s in PlaceStatus] + ["new", "summarized", "published", "error"]
        if body.processing_status not in valid_statuses:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        place.processing_status = body.processing_status
    
    if body.summary is not None:
        place.summary = body.summary.strip() if body.summary else None
    
    if body.tags_csv is not None:
        place.tags_csv = body.tags_csv.strip() if body.tags_csv else None
    
    # Обновляем теневые поля (Итерация 5)
    if body.attempts is not None:
        place.attempts = json.dumps(body.attempts)
    
    if body.quality_flags is not None:
        place.quality_flags = json.dumps(body.quality_flags)
    
    # Save changes
    try:
        db.add(place)
        db.commit()
        db.refresh(place)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    return AdminPlaceUpdateResponse(
        id=place.id,
        processing_status=place.processing_status,
        summary=place.summary,
        tags_csv=place.tags_csv
    )


@router.get("/places/stats")
def get_place_stats(
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin)
):
    """Get place statistics"""
    
    # Count by status (включая новые статусы)
    status_counts = {}
    all_statuses = [s.value for s in PlaceStatus] + ["new", "summarized", "published", "error"]
    for status in all_statuses:
        count = db.query(Place).filter(Place.processing_status == status).count()
        if count > 0:  # Показываем только статусы с местами
            status_counts[status] = count
    
    # Total count
    total = db.query(Place).count()
    
    return {
        "total": total,
        "by_status": status_counts,
        "published_percentage": round((status_counts.get("published", 0) / total * 100), 2) if total > 0 else 0
    }


@router.get("/places/{place_id}/events")
def get_place_events(
    place_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin)
):
    """Get events for a specific place"""
    
    # Find place
    place = db.query(Place).get(place_id)
    if not place:
        raise HTTPException(status_code=404, detail="Place not found")
    
    # Get events
    events = db.query(PlaceEvent).filter(
        PlaceEvent.place_id == place_id
    ).order_by(PlaceEvent.ts.desc()).all()
    
    # Convert to response format
    event_items = []
    for event in events:
        event_items.append({
            "id": event.id,
            "agent": event.agent,
            "code": event.code,
            "level": event.level,
            "note": event.note,
            "ts": event.ts
        })
    
    return {
        "place_id": place_id,
        "place_name": place.name,
        "total_events": len(events),
        "events": event_items
    }


@router.post("/search/refresh")
def refresh_search_mv(
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin)
):
    """Refresh materialized view for search (SECURITY DEFINER function)."""
    try:
        from sqlalchemy import text
        db.execute(text("SELECT epx.refresh_places_search_mv();"))
        db.commit()
        return {"ok": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Refresh failed: {e}")
