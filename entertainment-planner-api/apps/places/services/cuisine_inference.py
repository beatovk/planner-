#!/usr/bin/env python3
"""Cuisine inference service for dish-to-cuisine mapping"""

import os
import yaml
import logging
from typing import List, Dict, Set, Optional, Tuple
from sqlalchemy.orm import Session

from apps.places.models import Place

logger = logging.getLogger(__name__)


class CuisineInferenceService:
    """Service for inferring cuisines from dish tags"""
    
    def __init__(self):
        self.dish_to_cuisine = self._load_dish_mapping()
        
    def _load_dish_mapping(self) -> Dict[str, List[str]]:
        """Load dish-to-cuisine mapping from YAML config"""
        try:
            config_path = os.path.join(os.getcwd(), "config", "dish_to_cuisine.yml")
            if not os.path.exists(config_path):
                logger.warning(f"Dish mapping config not found at {config_path}")
                return {}
                
            with open(config_path, "r", encoding="utf-8") as f:
                mapping = yaml.safe_load(f) or {}
                
            # Normalize keys to lowercase
            normalized = {}
            for dish, cuisines in mapping.items():
                if isinstance(cuisines, list) and cuisines:
                    normalized[dish.lower().strip()] = [c.strip() for c in cuisines if c.strip()]
                    
            logger.info(f"Loaded {len(normalized)} dish-to-cuisine mappings")
            return normalized
            
        except Exception as e:
            logger.error(f"Failed to load dish mapping: {e}")
            return {}
    
    def infer_cuisines_from_dishes(self, tags_csv: str, text_blob: str = None) -> Tuple[List[str], Dict]:
        """
        Infer cuisines from dish tags in tags_csv
        
        Args:
            tags_csv: Comma-separated tags string
            text_blob: Optional text for fallback matching
            
        Returns:
            Tuple of (cuisines_to_add, evidence_dict)
        """
        # Parse tags
        tags = [t.strip().lower() for t in (tags_csv or "").split(",") if t.strip()]
        dishes = [t.split("dish:")[1] for t in tags if t.startswith("dish:") and ":" in t]
        
        proposed = []  # cuisines to add
        evidence = []
        
        # Process each dish
        for dish in dishes:
            if dish in self.dish_to_cuisine:
                cuisines = self.dish_to_cuisine[dish]
                if cuisines:
                    primary = cuisines[0]
                    proposed.append(primary)
                    
                    # Keep evidence for debugging
                    if len(cuisines) > 1:
                        evidence.append({"dish": dish, "primary": primary, "alternates": cuisines[1:]})
                    else:
                        evidence.append({"dish": dish, "primary": primary})
        
        # Optional text fallback (conservative)
        if not dishes and text_blob:
            text_lower = text_blob.lower()
            for dish, cuisines in self.dish_to_cuisine.items():
                if dish in text_lower and cuisines:
                    proposed.append(cuisines[0])
                    evidence.append({"text_hit": dish, "primary": cuisines[0]})
        
        # Remove duplicates while preserving order
        seen = set()
        unique_proposed = []
        for cuisine in proposed:
            if cuisine not in seen:
                seen.add(cuisine)
                unique_proposed.append(cuisine)
        
        # Filter out already present cuisines
        present_cuisines = {t.split("cuisine:")[1] for t in tags if t.startswith("cuisine:") and ":" in t}
        to_add = [c for c in unique_proposed if c not in present_cuisines]
        
        # Calculate confidence
        confidence = min(1.0, 0.5 + 0.15 * len(to_add))  # simple, conservative
        status = "applied" if to_add else "noop"
        
        return to_add, {
            "from_dishes": dishes,
            "proposed": to_add,
            "confidence": round(confidence, 2),
            "status": status,
            "evidence": evidence
        }
    
    def backfill_place(self, place: Place, db: Session) -> bool:
        """
        Backfill cuisine tags for a single place
        
        Args:
            place: Place instance
            db: Database session
            
        Returns:
            True if place was updated, False otherwise
        """
        try:
            # Compose text blob for fallback matching
            text_parts = []
            if place.name:
                text_parts.append(place.name)
            if place.summary:
                text_parts.append(place.summary)
            if place.description_full:
                text_parts.append(place.description_full)
            text_blob = " ".join(text_parts)
            
            # Infer cuisines
            to_add, signals = self.infer_cuisines_from_dishes(place.tags_csv or "", text_blob)
            
            if not to_add:
                return False  # nothing to do
            
            # Update tags_csv
            current_tags = [t.strip() for t in (place.tags_csv or "").split(",") if t.strip()]
            new_cuisine_tags = [f"cuisine:{c}" for c in to_add]
            updated_tags = current_tags + new_cuisine_tags
            
            # Remove duplicates while preserving order
            seen = set()
            unique_tags = []
            for tag in updated_tags:
                if tag not in seen:
                    seen.add(tag)
                    unique_tags.append(tag)
            
            place.tags_csv = ",".join(unique_tags) if unique_tags else None
            
            # Update signals
            current_signals = place.signals or {}
            current_signals["cuisine_inferred"] = signals
            place.signals = current_signals
            
            # Update category if we have cuisine tags but no category
            if not place.category and to_add:
                place.category = "restaurant"  # fallback category for places with cuisine
            
            db.commit()
            logger.debug(f"Updated place {place.id} with cuisines: {to_add}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to backfill place {place.id}: {e}")
            db.rollback()
            return False
    
    def backfill_all_places(self, db: Session, batch_size: int = 100) -> Dict[str, int]:
        """
        Backfill cuisine tags for all places
        
        Args:
            db: Database session
            batch_size: Number of places to process at once
            
        Returns:
            Statistics dictionary
        """
        stats = {
            "processed": 0,
            "updated": 0,
            "errors": 0
        }
        
        try:
            # Get places that have dish tags but no cuisine tags
            places = db.query(Place).filter(
                Place.tags_csv.like("%dish:%"),
                ~Place.tags_csv.like("%cuisine:%")
            ).limit(batch_size).all()
            
            logger.info(f"Found {len(places)} places with dish tags but no cuisine tags")
            
            for place in places:
                try:
                    if self.backfill_place(place, db):
                        stats["updated"] += 1
                    stats["processed"] += 1
                except Exception as e:
                    logger.error(f"Error processing place {place.id}: {e}")
                    stats["errors"] += 1
                    
        except Exception as e:
            logger.error(f"Failed to backfill places: {e}")
            stats["errors"] += 1
            
        return stats
