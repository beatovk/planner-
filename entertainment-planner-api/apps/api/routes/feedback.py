#!/usr/bin/env python3
"""Feedback API for user signals"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.core.db import get_db
from apps.places.schemas.vibes import FeedbackRequest
from apps.places.services.session_profiles import get_profile_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/feedback")
async def add_feedback(
    request: FeedbackRequest,
    db: Session = Depends(get_db)
):
    """
    Add user feedback signal to session profile.
    
    This endpoint collects user interactions to improve personalization:
    - like/unlike: positive/negative feedback
    - open: place card opened
    - add_to_route: added to route
    - dwell: time spent viewing (in milliseconds)
    
    Signals are used to update the user's vibe vector and novelty preference.
    """
    try:
        profile_service = get_profile_service()
        
        # Add feedback to profile
        success = profile_service.add_feedback(request)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to add feedback")
        
        logger.info(f"Added {request.action} signal for place {request.place_id} in session {request.session_id}")
        
        return {
            "message": "Feedback added successfully",
            "session_id": request.session_id,
            "place_id": request.place_id,
            "action": request.action
        }
        
    except Exception as e:
        logger.error(f"Failed to add feedback: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add feedback: {str(e)}")


@router.get("/feedback/profile/{session_id}")
async def get_profile_info(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get profile information for a session"""
    try:
        profile_service = get_profile_service()
        
        # Get profile stats
        stats = profile_service.get_profile_stats(session_id)
        
        if not stats["exists"]:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get profile info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get profile info: {str(e)}")


@router.get("/feedback/profile/{session_id}/vibes")
async def get_top_vibes(
    session_id: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get top vibes for a session"""
    try:
        profile_service = get_profile_service()
        
        # Get top vibes
        top_vibes = profile_service.get_top_vibes(session_id, limit)
        
        return {
            "session_id": session_id,
            "top_vibes": top_vibes,
            "count": len(top_vibes)
        }
        
    except Exception as e:
        logger.error(f"Failed to get top vibes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get top vibes: {str(e)}")


@router.get("/feedback/profile/{session_id}/activity")
async def get_recent_activity(
    session_id: str,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get recent activity for a session"""
    try:
        profile_service = get_profile_service()
        
        # Get recent activity
        activity = profile_service.get_recent_activity(session_id, limit)
        
        return {
            "session_id": session_id,
            "recent_activity": activity,
            "count": len(activity)
        }
        
    except Exception as e:
        logger.error(f"Failed to get recent activity: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recent activity: {str(e)}")


@router.delete("/feedback/profile/{session_id}")
async def reset_profile(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Reset profile for a session"""
    try:
        profile_service = get_profile_service()
        
        # Reset profile
        success = profile_service.reset_profile(session_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        return {
            "message": "Profile reset successfully",
            "session_id": session_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reset profile: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset profile: {str(e)}")


@router.get("/feedback/stats")
async def get_feedback_stats(db: Session = Depends(get_db)):
    """Get global feedback statistics"""
    try:
        profile_service = get_profile_service()
        
        # Get global stats
        stats = profile_service.get_stats()
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get feedback stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get feedback stats: {str(e)}")


@router.post("/feedback/cleanup")
async def cleanup_expired_profiles(db: Session = Depends(get_db)):
    """Clean up expired profiles (admin endpoint)"""
    try:
        profile_service = get_profile_service()
        
        # Clean up expired profiles
        removed_count = profile_service.cleanup_expired_profiles()
        
        return {
            "message": f"Cleaned up {removed_count} expired profiles",
            "removed_count": removed_count
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup profiles: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup profiles: {str(e)}")
