#!/usr/bin/env python3
"""Backfill cuisine inference for existing places"""

import argparse
import logging
import sys
from typing import Dict, Any

from sqlalchemy.orm import Session
from apps.core.db import SessionLocal
from apps.places.models import Place
from apps.places.services.cuisine_inference import CuisineInferenceService

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backfill_cuisines(batch_size: int = 100, dry_run: bool = False) -> Dict[str, Any]:
    """
    Backfill cuisine tags for existing places
    
    Args:
        batch_size: Number of places to process at once
        dry_run: If True, only show what would be done without making changes
        
    Returns:
        Statistics dictionary
    """
    db = SessionLocal()
    stats = {
        "total_places": 0,
        "places_with_dishes": 0,
        "places_with_cuisines": 0,
        "places_updated": 0,
        "errors": 0,
        "dry_run": dry_run
    }
    
    try:
        # Инициализируем сервис
        cuisine_service = CuisineInferenceService()
        
        # Получаем общую статистику
        total_places = db.query(Place).count()
        places_with_dishes = db.query(Place).filter(
            Place.tags_csv.like("%dish:%")
        ).count()
        places_with_cuisines = db.query(Place).filter(
            Place.tags_csv.like("%cuisine:%")
        ).count()
        
        stats.update({
            "total_places": total_places,
            "places_with_dishes": places_with_dishes,
            "places_with_cuisines": places_with_cuisines
        })
        
        logger.info(f"Database stats:")
        logger.info(f"  Total places: {total_places}")
        logger.info(f"  Places with dish tags: {places_with_dishes}")
        logger.info(f"  Places with cuisine tags: {places_with_cuisines}")
        
        if dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
        
        # Получаем места для обработки
        places_to_process = db.query(Place).filter(
            Place.tags_csv.like("%dish:%"),
            ~Place.tags_csv.like("%cuisine:%")
        ).limit(batch_size).all()
        
        logger.info(f"Found {len(places_to_process)} places with dish tags but no cuisine tags")
        
        if not places_to_process:
            logger.info("No places need cuisine inference")
            return stats
        
        # Обрабатываем места
        for place in places_to_process:
            try:
                logger.info(f"Processing place {place.id}: {place.name}")
                
                if dry_run:
                    # В dry run режиме только показываем, что будет сделано
                    text_parts = []
                    if place.name:
                        text_parts.append(place.name)
                    if place.summary:
                        text_parts.append(place.summary)
                    if place.description_full:
                        text_parts.append(place.description_full)
                    text_blob = " ".join(text_parts)
                    
                    cuisines_to_add, evidence = cuisine_service.infer_cuisines_from_dishes(
                        place.tags_csv or "", text_blob
                    )
                    
                    if cuisines_to_add:
                        logger.info(f"  Would add cuisines: {cuisines_to_add}")
                        logger.info(f"  Evidence: {evidence}")
                        stats["places_updated"] += 1
                    else:
                        logger.info(f"  No cuisines to add")
                else:
                    # Реальная обработка
                    if cuisine_service.backfill_place(place, db):
                        stats["places_updated"] += 1
                        logger.info(f"  Updated with cuisines")
                    else:
                        logger.info(f"  No cuisines to add")
                        
            except Exception as e:
                logger.error(f"Error processing place {place.id}: {e}")
                stats["errors"] += 1
        
        if not dry_run:
            db.commit()
            logger.info("Changes committed to database")
        
    except Exception as e:
        logger.error(f"Fatal error in backfill: {e}")
        stats["errors"] += 1
        if not dry_run:
            db.rollback()
    finally:
        db.close()
    
    return stats


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Backfill cuisine inference for existing places")
    parser.add_argument(
        "--batch-size", 
        type=int, 
        default=100, 
        help="Number of places to process at once (default: 100)"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Show what would be done without making changes"
    )
    
    args = parser.parse_args()
    
    try:
        stats = backfill_cuisines(
            batch_size=args.batch_size,
            dry_run=args.dry_run
        )
        
        logger.info("Backfill completed!")
        logger.info(f"Statistics: {stats}")
        
        if stats["errors"] > 0:
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
