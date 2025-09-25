#!/usr/bin/env python3
"""Session profiles service for user personalization"""

import time
import logging
from typing import Dict, List, Optional, Any
from collections import defaultdict

from apps.places.schemas.vibes import SessionProfile, FeedbackRequest

logger = logging.getLogger(__name__)


class SessionProfileService:
    """Service for managing user session profiles"""
    
    def __init__(self):
        self.profiles: Dict[str, SessionProfile] = {}
        self.session_ttl = 24 * 60 * 60  # 24 hours in seconds
        self.max_signals = 100
        
    def get_profile(self, session_id: str) -> Optional[SessionProfile]:
        """Get user profile by session ID"""
        if session_id not in self.profiles:
            return None
        
        profile = self.profiles[session_id]
        
        # Check if profile is expired
        if time.time() - profile.created_at > self.session_ttl:
            del self.profiles[session_id]
            return None
        
        return profile
    
    def create_profile(self, session_id: str) -> SessionProfile:
        """Create new user profile"""
        profile = SessionProfile(session_id=session_id)
        self.profiles[session_id] = profile
        
        logger.debug(f"Created profile for session {session_id}")
        return profile
    
    def get_or_create_profile(self, session_id: str) -> SessionProfile:
        """Get existing profile or create new one"""
        profile = self.get_profile(session_id)
        if not profile:
            profile = self.create_profile(session_id)
        return profile
    
    def add_feedback(self, request: FeedbackRequest) -> bool:
        """Add user feedback signal to profile"""
        try:
            profile = self.get_or_create_profile(request.session_id)
            
            # Add signal
            profile.add_signal(
                place_id=request.place_id,
                action=request.action,
                dwell_ms=request.dwell_ms,
                step=request.step
            )
            
            # Update vibe vector if it's a positive signal
            if request.action in ["like", "add_to_route"]:
                # This would need place data to update vibe vector
                # For now, just log the action
                logger.debug(f"Added {request.action} signal for place {request.place_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to add feedback: {e}")
            return False
    
    def update_search_signal(self, session_id: str, steps: List[Dict[str, Any]], vibes: List[str]):
        """Update profile with search signals"""
        try:
            profile = self.get_or_create_profile(session_id)
            
            # Update last areas based on search context
            # This is a simplified implementation
            if steps:
                # Extract area information from steps if available
                areas = []
                for step in steps:
                    query = step.get('query', '')
                    # Simple area extraction - could be enhanced
                    if 'thonglor' in query.lower():
                        areas.append('thonglor')
                    elif 'sukhumvit' in query.lower():
                        areas.append('sukhumvit')
                    elif 'silom' in query.lower():
                        areas.append('silom')
                
                if areas:
                    profile.last_areas = areas[-3:]  # Keep last 3 areas
            
            # Update novelty preference based on vibes
            if vibes:
                novelty_indicators = ['hidden_gem', 'artsy', 'unique', 'new', 'different']
                novelty_count = sum(1 for vibe in vibes if vibe in novelty_indicators)
                if novelty_count > 0:
                    profile.novelty_preference = min(0.8, profile.novelty_preference + 0.1)
            
            logger.debug(f"Updated search signals for session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to update search signals: {e}")
    
    def get_profile_stats(self, session_id: str) -> Dict[str, Any]:
        """Get profile statistics"""
        profile = self.get_profile(session_id)
        if not profile:
            return {"exists": False}
        
        return {
            "exists": True,
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
            "vibe_vector_size": len(profile.vibe_vector),
            "signals_count": len(profile.signals),
            "last_areas": profile.last_areas,
            "novelty_preference": profile.novelty_preference
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get global profile statistics"""
        current_time = time.time()
        
        # Count active profiles
        active_profiles = 0
        expired_profiles = 0
        
        for profile in self.profiles.values():
            if current_time - profile.created_at <= self.session_ttl:
                active_profiles += 1
            else:
                expired_profiles += 1
        
        # Calculate average signals per profile
        total_signals = sum(len(profile.signals) for profile in self.profiles.values())
        avg_signals = total_signals / len(self.profiles) if self.profiles else 0
        
        return {
            "total_profiles": len(self.profiles),
            "active_profiles": active_profiles,
            "expired_profiles": expired_profiles,
            "total_signals": total_signals,
            "avg_signals_per_profile": avg_signals,
            "session_ttl_hours": self.session_ttl / 3600
        }
    
    def cleanup_expired_profiles(self) -> int:
        """Remove expired profiles and return count of removed profiles"""
        current_time = time.time()
        expired_keys = []
        
        for session_id, profile in self.profiles.items():
            if current_time - profile.created_at > self.session_ttl:
                expired_keys.append(session_id)
        
        for session_id in expired_keys:
            del self.profiles[session_id]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired profiles")
        
        return len(expired_keys)
    
    def get_top_vibes(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top vibes for a session"""
        profile = self.get_profile(session_id)
        if not profile or not profile.vibe_vector:
            return []
        
        # Sort vibes by weight
        sorted_vibes = sorted(
            profile.vibe_vector.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [
            {"vibe": vibe, "weight": weight}
            for vibe, weight in sorted_vibes[:limit]
        ]
    
    def get_recent_activity(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent activity for a session"""
        profile = self.get_profile(session_id)
        if not profile:
            return []
        
        # Return recent signals
        recent_signals = profile.signals[-limit:] if profile.signals else []
        
        return [
            {
                "place_id": signal["place_id"],
                "action": signal["action"],
                "dwell_ms": signal.get("dwell_ms"),
                "step": signal.get("step"),
                "timestamp": signal["timestamp"]
            }
            for signal in recent_signals
        ]
    
    def reset_profile(self, session_id: str) -> bool:
        """Reset profile for a session"""
        try:
            if session_id in self.profiles:
                del self.profiles[session_id]
                logger.info(f"Reset profile for session {session_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to reset profile: {e}")
            return False


# Global instance
_profile_service = None


def get_profile_service() -> SessionProfileService:
    """Get global profile service instance"""
    global _profile_service
    if _profile_service is None:
        _profile_service = SessionProfileService()
    return _profile_service
