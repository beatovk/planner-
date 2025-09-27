"""Health check endpoints exposed by the public API."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.core.db import get_db
from apps.core.feature_flags import get_feature_flags, get_slotter_config
from apps.places.services.synonyms_validator import get_synonyms_health

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("", summary="Constant-time readiness probe")
def health_fast() -> dict[str, str]:
    """Simple readiness probe that avoids touching the database."""
    return {"status": "ok", "timestamp": _utc_timestamp()}


@router.get("/db", summary="Database connectivity check")
def health_db(db: Session = Depends(get_db)) -> dict[str, str]:
    """Deep health check that validates the database connection."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "scope": "db", "timestamp": _utc_timestamp()}


@router.get("/synonyms", summary="Synonyms dataset status")
def synonyms_health_check() -> dict[str, object]:
    try:
        metrics = get_synonyms_health()
        return {
            "status": "healthy" if metrics["is_healthy"] else "unhealthy",
            "metrics": metrics,
            "timestamp": _utc_timestamp(),
        }
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Synonyms health check failed: %s", exc)
        return {
            "status": "unhealthy",
            "error": str(exc),
            "timestamp": _utc_timestamp(),
        }


@router.get("/detailed", summary="Aggregated component status")
def detailed_health_check(db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
        synonyms_metrics = get_synonyms_health()
        synonyms_status = "healthy" if synonyms_metrics["is_healthy"] else "unhealthy"
        overall_status = "healthy" if db_status == "connected" and synonyms_status == "healthy" else "unhealthy"
        return {
            "status": overall_status,
            "components": {
                "database": {"status": db_status},
                "synonyms": {"status": synonyms_status, "details": synonyms_metrics},
            },
            "timestamp": _utc_timestamp(),
        }
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Detailed health check failed: %s", exc)
        return {
            "status": "unhealthy",
            "error": str(exc),
            "timestamp": _utc_timestamp(),
        }


@router.get("/feature-flags", summary="Feature flag snapshot")
def health_feature_flags() -> dict[str, object]:
    try:
        flags = get_feature_flags()
        config = get_slotter_config()
        return {
            "ok": True,
            "flags": flags.get_all_flags(),
            "slotter_config": config,
            "timestamp": _utc_timestamp(),
        }
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Feature flag health check failed: %s", exc)
        return {"ok": False, "error": str(exc), "timestamp": _utc_timestamp()}

