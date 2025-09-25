"""
Health check endpoints для мониторинга системы.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from apps.core.db import get_db
from apps.places.services.synonyms_validator import get_synonyms_health
from apps.core.feature_flags import get_feature_flags, get_slotter_config
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Основной health check endpoint."""
    try:
        # Проверяем подключение к БД
        db.execute("SELECT 1")
        
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": "2025-01-21T10:00:00Z"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": "2025-01-21T10:00:00Z"
        }


@router.get("/health/synonyms")
async def synonyms_health_check():
    """Health check для словаря синонимов."""
    try:
        metrics = get_synonyms_health()
        
        return {
            "status": "healthy" if metrics["is_healthy"] else "unhealthy",
            "metrics": metrics,
            "timestamp": "2025-01-21T10:00:00Z"
        }
    except Exception as e:
        logger.error(f"Synonyms health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": "2025-01-21T10:00:00Z"
        }


@router.get("/health/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """Детальный health check с метриками всех компонентов."""
    try:
        # Проверяем БД
        db.execute("SELECT 1")
        db_status = "connected"
        
        # Проверяем словарь синонимов
        synonyms_metrics = get_synonyms_health()
        synonyms_status = "healthy" if synonyms_metrics["is_healthy"] else "unhealthy"
        
        # Общий статус
        overall_status = "healthy" if db_status == "connected" and synonyms_status == "healthy" else "unhealthy"
        
        return {
            "status": overall_status,
            "components": {
                "database": {
                    "status": db_status,
                    "details": "PostgreSQL connection active"
                },
                "synonyms": {
                    "status": synonyms_status,
                    "details": synonyms_metrics
                }
            },
            "timestamp": "2025-01-21T10:00:00Z"
        }
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": "2025-01-21T10:00:00Z"
        }


@router.get("/health/feature-flags")
def health_feature_flags():
    """Feature flags health check endpoint."""
    try:
        flags = get_feature_flags()
        config = get_slotter_config()
        return {
            "ok": True,
            "flags": flags.get_all_flags(),
            "slotter_config": config,
            "timestamp": "2025-01-21T10:00:00Z"
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}