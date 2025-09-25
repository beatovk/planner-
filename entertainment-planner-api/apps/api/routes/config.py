"""Configuration endpoint for frontend"""

from fastapi import APIRouter, HTTPException
from apps.core.config import settings
from pydantic import BaseModel

router = APIRouter()


class ConfigResponse(BaseModel):
    google_maps_api_key: str


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    """Get configuration for frontend"""
    try:
        return ConfigResponse(
            google_maps_api_key=settings.google_maps_api_key
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Configuration error: {str(e)}")
