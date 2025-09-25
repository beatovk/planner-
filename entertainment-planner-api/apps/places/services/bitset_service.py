#!/usr/bin/env python3
"""Bitset service for O(1) vibe_score calculation"""

import hashlib
import logging
from typing import List, Dict, Set, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text

from apps.places.models import Place
from apps.places.schemas.vibes import VibesOntology

logger = logging.getLogger(__name__)


class BitsetService:
    """Service for bitset operations and vibe scoring"""
    
    def __init__(self, ontology: VibesOntology):
        self.ontology = ontology
        self.max_bits = 64  # PostgreSQL INTEGER supports 64-bit; use full width
        self.tag_to_bit = self._build_tag_to_bit_map()
        self.bit_to_tag = {bit: tag for tag, bit in self.tag_to_bit.items()}
        
    def _build_tag_to_bit_map(self) -> Dict[str, int]:
        """Build mapping from tag to bit position (stable order from config/bitset_order.yml if present)."""
        import os, yaml
        tag_to_bit: Dict[str, int] = {}
        fixed: list = []
        try:
            path = os.path.join(os.getcwd(), "config", "bitset_order.yml")
            if os.path.exists(path):
                cfg = yaml.safe_load(open(path, "r", encoding="utf-8"))
                fixed = [str(x).strip().lower() for x in (cfg.get("order") or []) if x]
        except Exception as e:
            logger.warning(f"bitset_order.yml load failed: {e}")
        bit_pos = 0
        # 1) фиксированные теги
        for tag in fixed:
            if bit_pos >= self.max_bits: break
            if tag and tag not in tag_to_bit:
                tag_to_bit[tag] = bit_pos; bit_pos += 1
        # 2) добиваем из онтологии (стабильный алфавит по id)
        all_tags = set()
        for item_list in self.ontology.get_all_items().values():
            for item in item_list:
                all_tags.add(item.id.lower().strip())
        for tag in sorted(all_tags):
            if bit_pos >= self.max_bits: break
            if tag not in tag_to_bit:
                tag_to_bit[tag] = bit_pos; bit_pos += 1
        logger.info(f"Built tag-to-bit mapping for {len(tag_to_bit)} tags (fixed={len(fixed)})")
        return tag_to_bit
    
    def tags_to_bitset(self, tags: List[str]) -> int:
        """Convert list of tags to bitset integer"""
        bitset = 0
        for tag in tags:
            tag_lower = tag.lower().strip()
            if tag_lower in self.tag_to_bit:
                bit_pos = self.tag_to_bit[tag_lower]
                bitset |= (1 << bit_pos)
        return bitset
    
    def bitset_to_tags(self, bitset: int) -> List[str]:
        """Convert bitset integer to list of tags"""
        tags = []
        for bit_pos in range(self.max_bits):
            if bitset & (1 << bit_pos):
                if bit_pos in self.bit_to_tag:
                    tags.append(self.bit_to_tag[bit_pos])
        return tags
    
    def calculate_vibe_score(self, place_bitset: int, profile_bitset: int) -> float:
        """Calculate Jaccard similarity between two bitsets - O(1) operation"""
        if place_bitset == 0 and profile_bitset == 0:
            return 0.0
        
        # Calculate intersection and union using bitwise operations
        intersection = place_bitset & profile_bitset
        union = place_bitset | profile_bitset
        
        # Count set bits (popcount)
        intersection_count = bin(intersection).count('1')
        union_count = bin(union).count('1')
        
        if union_count == 0:
            return 0.0
        
        return intersection_count / union_count
    
    def calculate_vibe_score_with_weights(self, place_bitset: int, profile_vector: Dict[str, float]) -> float:
        """Calculate weighted vibe score using profile vector"""
        if not profile_vector or place_bitset == 0:
            return 0.0
        
        total_score = 0.0
        total_weight = 0.0
        
        for tag, weight in profile_vector.items():
            tag_lower = tag.lower().strip()
            if tag_lower in self.tag_to_bit:
                bit_pos = self.tag_to_bit[tag_lower]
                if place_bitset & (1 << bit_pos):
                    total_score += weight
                total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        return total_score / total_weight
    
    def update_place_bitset(self, db: Session, place_id: int) -> bool:
        """Update bitset for a specific place"""
        try:
            place = db.query(Place).filter(Place.id == place_id).first()
            if not place or not place.tags_csv:
                return False
            
            # Parse tags from CSV
            tags = [tag.strip() for tag in place.tags_csv.split(',') if tag.strip()]
            
            # Convert to bitset
            bitset = self.tags_to_bitset(tags)
            
            # Update place
            place.tag_bitset = bitset
            db.commit()
            
            logger.debug(f"Updated bitset for place {place_id}: {bitset}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update bitset for place {place_id}: {e}")
            db.rollback()
            return False
    
    def update_all_places_bitsets(self, db: Session, batch_size: int = 100) -> int:
        """Update bitsets for all places in batches"""
        updated_count = 0
        
        try:
            # Get all places with tags
            places = db.query(Place).filter(
                Place.tags_csv.isnot(None),
                Place.tags_csv != ''
            ).all()
            
            total_places = len(places)
            logger.info(f"Updating bitsets for {total_places} places")
            
            for i in range(0, total_places, batch_size):
                batch = places[i:i + batch_size]
                
                for place in batch:
                    if self.update_place_bitset(db, place.id):
                        updated_count += 1
                
                if (i + batch_size) % 1000 == 0:
                    logger.info(f"Processed {i + batch_size}/{total_places} places")
            
            logger.info(f"Updated bitsets for {updated_count}/{total_places} places")
            return updated_count
            
        except Exception as e:
            logger.error(f"Failed to update bitsets: {e}")
            return updated_count
    
    def get_category_id(self, category: str) -> int:
        """Get numeric ID for category (for MMR)"""
        # Simple hash-based ID generation
        return hash(category) % 10000
    
    def generate_sig_hash(self, place: Place) -> str:
        """Generate signature hash for MMR diversity"""
        # Combine key attributes for diversity calculation
        sig_data = f"{place.name}_{place.category}_{place.tags_csv}_{place.lat}_{place.lng}"
        return hashlib.md5(sig_data.encode()).hexdigest()[:16]
    
    def update_place_metadata(self, db: Session, place_id: int) -> bool:
        """Update all metadata for a place (bitset, category_id, sig_hash)"""
        try:
            place = db.query(Place).filter(Place.id == place_id).first()
            if not place:
                return False
            
            # Update bitset
            if place.tags_csv:
                tags = [tag.strip() for tag in place.tags_csv.split(',') if tag.strip()]
                place.tag_bitset = self.tags_to_bitset(tags)
            
            # Update category_id
            if place.category:
                place.category_id = self.get_category_id(place.category)
            
            # Update sig_hash
            place.sig_hash = self.generate_sig_hash(place)
            
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to update metadata for place {place_id}: {e}")
            db.rollback()
            return False
    
    def get_places_by_bitset(self, db: Session, bitset: int, limit: int = 100) -> List[Place]:
        """Get places that have any tags matching the bitset"""
        try:
            # Use bitwise AND to find places with matching tags
            places = db.query(Place).filter(
                Place.tag_bitset.isnot(None),
                Place.tag_bitset.op('&')(bitset) > 0,
                Place.processing_status.in_(['published', 'summarized'])
            ).limit(limit).all()
            
            return places
            
        except Exception as e:
            logger.error(f"Failed to get places by bitset: {e}")
            return []
    
    def get_similar_places(self, db: Session, place_id: int, limit: int = 10) -> List[Tuple[Place, float]]:
        """Get places similar to the given place based on bitset similarity"""
        try:
            place = db.query(Place).filter(Place.id == place_id).first()
            if not place or not place.tag_bitset:
                return []
            
            # Get all places with bitsets
            places = db.query(Place).filter(
                Place.tag_bitset.isnot(None),
                Place.id != place_id,
                Place.processing_status.in_(['published', 'summarized'])
            ).all()
            
            # Calculate similarities
            similarities = []
            for p in places:
                similarity = self.calculate_vibe_score(place.tag_bitset, p.tag_bitset)
                if similarity > 0:
                    similarities.append((p, similarity))
            
            # Sort by similarity and return top results
            similarities.sort(key=lambda x: x[1], reverse=True)
            return similarities[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get similar places: {e}")
            return []
    
    def get_stats(self, db: Session) -> Dict[str, int]:
        """Get statistics about bitset usage"""
        try:
            total_places = db.query(Place).count()
            places_with_bitset = db.query(Place).filter(Place.tag_bitset.isnot(None)).count()
            places_with_tags = db.query(Place).filter(
                Place.tags_csv.isnot(None),
                Place.tags_csv != ''
            ).count()
            
            return {
                "total_places": total_places,
                "places_with_bitset": places_with_bitset,
                "places_with_tags": places_with_tags,
                "bitset_coverage": places_with_bitset / total_places if total_places > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get bitset stats: {e}")
            return {}


def create_bitset_service(ontology: VibesOntology) -> BitsetService:
    """Create bitset service with ontology"""
    return BitsetService(ontology)
