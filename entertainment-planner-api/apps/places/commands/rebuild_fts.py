#!/usr/bin/env python3
"""Command to rebuild FTS5 index"""

import sys
import os
import logging
from sqlalchemy import text
from apps.core.db import SessionLocal

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)


def rebuild_fts_index():
    """Rebuild FTS5 index from scratch"""
    logger.info("Starting FTS5 index rebuild...")
    
    db = SessionLocal()
    try:
        # Step 1: Clear existing FTS5 data
        logger.info("Clearing existing FTS5 data...")
        db.execute(text("DELETE FROM fts_places;"))
        
        # Step 2: Rebuild FTS5 index with all published places
        logger.info("Rebuilding FTS5 index...")
        db.execute(text("""
            INSERT INTO fts_places(rowid, name, tags_csv, summary, category, description_full, address)
            SELECT id, name, tags_csv, summary, category, description_full, address
            FROM places
            WHERE processing_status = 'published';
        """))
        
        # Step 3: Optimize FTS5 index
        logger.info("Optimizing FTS5 index...")
        db.execute(text("INSERT INTO fts_places(fts_places) VALUES('optimize');"))
        
        # Step 4: Get statistics
        result = db.execute(text("SELECT COUNT(*) as count FROM fts_places;"))
        count = result.fetchone().count
        
        logger.info(f"FTS5 index rebuilt successfully! Indexed {count} places.")
        
        # Commit changes
        db.commit()
        
    except Exception as e:
        logger.error(f"Error rebuilding FTS5 index: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def main():
    """Main function"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        rebuild_fts_index()
        print("✅ FTS5 index rebuilt successfully!")
    except Exception as e:
        print(f"❌ Error rebuilding FTS5 index: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
