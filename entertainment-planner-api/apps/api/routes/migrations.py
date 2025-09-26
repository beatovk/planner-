#!/usr/bin/env python3
"""Migrations API endpoint for applying database migrations"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from apps.core.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/migrations/apply-epx-schema")
async def apply_epx_schema(db: Session = Depends(get_db)):
    """Apply epx schema and materialized view migration"""
    try:
        # Create epx schema
        db.execute(text("CREATE SCHEMA IF NOT EXISTS epx;"))
        
        # Create materialized view
        db.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS epx.places_search_mv AS
            SELECT 
                id,
                name,
                category,
                tags_csv,
                summary,
                lat,
                lng,
                picture_url,
                processing_status,
                search_vector,
                updated_at,
                published_at
            FROM places
            WHERE processing_status IN ('summarized', 'published')
        """))
        
        # Create refresh function
        db.execute(text("""
            CREATE OR REPLACE FUNCTION epx.refresh_places_search_mv()
            RETURNS void AS $$
            BEGIN
                REFRESH MATERIALIZED VIEW epx.places_search_mv;
                
                -- Update heartbeat
                INSERT INTO epx.mv_refresh_heartbeat (mv_name, refreshed_at)
                VALUES ('places_search_mv', now())
                ON CONFLICT (mv_name) 
                DO UPDATE SET refreshed_at = now();
            END;
            $$ LANGUAGE plpgsql;
        """))
        
        # Create heartbeat table
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS epx.mv_refresh_heartbeat (
                mv_name VARCHAR(100) PRIMARY KEY,
                refreshed_at TIMESTAMP WITH TIME ZONE NOT NULL
            );
        """))
        
        # Create indexes
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_places_search_mv_processing_status 
            ON epx.places_search_mv(processing_status);
        """))
        
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_places_search_mv_search_vector 
            ON epx.places_search_mv USING GIN(search_vector);
        """))
        
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_places_search_mv_tags_csv 
            ON epx.places_search_mv USING GIN(to_tsvector('english', tags_csv));
        """))
        
        # Refresh the materialized view
        db.execute(text("SELECT epx.refresh_places_search_mv();"))
        
        db.commit()
        
        return {
            "status": "success",
            "message": "epx schema and materialized view created successfully"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to apply epx schema: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to apply epx schema: {str(e)}")

@router.get("/migrations/status")
async def get_migration_status(db: Session = Depends(get_db)):
    """Get migration status"""
    try:
        # Check if epx schema exists
        schema_exists = db.execute(text("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.schemata 
                WHERE schema_name = 'epx'
            );
        """)).scalar()
        
        if not schema_exists:
            return {
                "epx_schema": False,
                "places_search_mv": False,
                "status": "epx schema not created"
            }
        
        # Check if materialized view exists
        mv_exists = db.execute(text("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'epx' 
                AND table_name = 'places_search_mv'
            );
        """)).scalar()
        
        if not mv_exists:
            return {
                "epx_schema": True,
                "places_search_mv": False,
                "status": "epx schema exists but materialized view not created"
            }
        
        # Get row count
        row_count = db.execute(text("SELECT COUNT(*) FROM epx.places_search_mv")).scalar()
        
        return {
            "epx_schema": True,
            "places_search_mv": True,
            "row_count": row_count,
            "status": "epx schema and materialized view ready"
        }
        
    except Exception as e:
        logger.error(f"Failed to get migration status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get migration status: {str(e)}")
