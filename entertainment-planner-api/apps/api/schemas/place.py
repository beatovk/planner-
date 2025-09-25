from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class PlaceBase(BaseModel):
    # Чистые поля (только используемые во фронтенде)
    name: Optional[str] = None
    category: Optional[str] = None
    summary: Optional[str] = None
    tags_csv: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    picture_url: Optional[str] = None
    gmaps_place_id: Optional[str] = None
    gmaps_url: Optional[str] = None
    rating: Optional[float] = None


class PlaceCreate(PlaceBase):
    # Источник и аудит
    source: str
    source_url: str
    raw_payload: str
    scraped_at: datetime
    
    # Координаты (обязательные для создания)
    lat: float
    lng: float


class PlaceUpdate(PlaceBase):
    # Процесс/модерация
    processing_status: Optional[str] = None
    last_error: Optional[str] = None
    published_at: Optional[datetime] = None


class PlaceResponse(PlaceBase):
    id: int
    processing_status: str
    updated_at: datetime
    published_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PlaceDetail(PlaceResponse):
    # Полная информация включая сырые данные
    source: str
    source_url: str
    raw_payload: str
    scraped_at: datetime
    last_error: Optional[str] = None
