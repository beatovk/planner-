#!/usr/bin/env python3
"""
Pydantic DTO для протокола агентов
Итерация 3: DTO и адаптеры
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from apps.places.models import Place, PlaceStatus


class PlaceDTO(BaseModel):
    """Единый контракт данных для протокола агентов"""
    
    # Идентификация
    place_id_internal: int
    source_url: Optional[str] = None
    
    # Сырые данные
    raw: Dict[str, Any] = Field(default_factory=dict)
    
    # Чистые данные
    clean: Dict[str, Any] = Field(default_factory=dict)
    
    # Google данные
    google: Dict[str, Any] = Field(default_factory=dict)
    
    # Статус и попытки
    status: str = PlaceStatus.NEW.value
    attempts: Dict[str, int] = Field(default_factory=lambda: {"summarizer": 0, "enricher": 0, "editor_cycles": 0})
    
    # Диагностика и история
    diagnostics: List[Dict[str, Any]] = Field(default_factory=list)
    history: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Флаги качества
    quality_flags: Dict[str, str] = Field(default_factory=lambda: {
        "summary": "unknown", 
        "tags": "unknown", 
        "photos": "unknown", 
        "coords": "unknown"
    })
    
    @classmethod
    def from_db(cls, place: Place) -> 'PlaceDTO':
        """Создать DTO из модели Place"""
        import json
        
        # Парсим JSON поля
        attempts = {}
        if place.attempts:
            try:
                attempts = json.loads(place.attempts)
            except (json.JSONDecodeError, TypeError):
                attempts = {"summarizer": 0, "enricher": 0, "editor_cycles": 0}
        
        quality_flags = {}
        if place.quality_flags:
            try:
                quality_flags = json.loads(place.quality_flags)
            except (json.JSONDecodeError, TypeError):
                quality_flags = {"summary": "unknown", "tags": "unknown", "photos": "unknown", "coords": "unknown"}
        
        return cls(
            place_id_internal=place.id,
            source_url=place.source_url,
            raw={
                "title": place.name,
                "description": place.description_full,
                "payload": place.raw_payload
            },
            clean={
                "name": place.name,
                "category": place.category,
                "tags_csv": place.tags_csv,
                "summary": place.summary,
                "full_description": place.description_full
            },
            google={
                "place_id": place.gmaps_place_id,
                "coords": {"lat": place.lat, "lng": place.lng},
                "maps_url": place.gmaps_url,
                "photos": [place.picture_url] if place.picture_url else []
            },
            status=place.processing_status,
            attempts=attempts,
            quality_flags=quality_flags
        )
    
    def to_db_patch(self) -> Dict[str, Any]:
        """Создать патч для обновления модели Place"""
        import json
        
        patch = {}
        
        # Обновляем основные поля
        if "name" in self.clean:
            patch["name"] = self.clean["name"]
        if "category" in self.clean:
            patch["category"] = self.clean["category"]
        if "tags_csv" in self.clean:
            patch["tags_csv"] = self.clean["tags_csv"]
        if "summary" in self.clean:
            patch["summary"] = self.clean["summary"]
        if "full_description" in self.clean:
            patch["description_full"] = self.clean["full_description"]
        
        # Обновляем Google поля
        if "place_id" in self.google:
            patch["gmaps_place_id"] = self.google["place_id"]
        if "coords" in self.google:
            coords = self.google["coords"]
            if coords and "lat" in coords and "lng" in coords:
                patch["lat"] = coords["lat"]
                patch["lng"] = coords["lng"]
        if "maps_url" in self.google:
            patch["gmaps_url"] = self.google["maps_url"]
        if "photos" in self.google and self.google["photos"]:
            patch["picture_url"] = self.google["photos"][0]
        
        # Обновляем статус
        patch["processing_status"] = self.status
        
        # Обновляем JSON поля
        patch["attempts"] = json.dumps(self.attempts)
        patch["quality_flags"] = json.dumps(self.quality_flags)
        
        return patch
    
    def add_diagnostic(self, agent: str, level: str, code: str, note: str = None):
        """Добавить диагностическое сообщение"""
        self.diagnostics.append({
            "agent": agent,
            "level": level,
            "code": code,
            "note": note,
            "ts": datetime.now().isoformat()
        })
    
    def add_history(self, from_agent: str, diff: str):
        """Добавить запись в историю"""
        self.history.append({
            "from": from_agent,
            "diff": diff,
            "ts": datetime.now().isoformat()
        })
    
    def increment_attempt(self, agent: str):
        """Увеличить счетчик попыток агента"""
        self.attempts[agent] = self.attempts.get(agent, 0) + 1
    
    def update_quality_flag(self, flag: str, value: str):
        """Обновить флаг качества"""
        self.quality_flags[flag] = value
