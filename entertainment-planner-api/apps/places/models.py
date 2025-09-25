import math
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, JSON, CheckConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from apps.core.db import Base


class PlaceStatus(Enum):
    """Статусы места для протокола агентов"""
    NEW = "new"                           # существующий
    SUMMARIZED = "summarized"             # новый
    ENRICHED = "enriched"                 # новый
    NEEDS_REVISION = "needs_revision"     # новый
    REVIEW_PENDING = "review_pending"     # новый
    PUBLISHED = "published"               # существующий
    FAILED = "failed"                     # новый
    ERROR = "error"                       # существующий (для совместимости)


class Place(Base):
    __tablename__ = "places"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Источник и аудит
    source = Column(Text)  # метка источника (timeout)
    source_url = Column(Text, unique=True)  # оригинальная страница
    raw_payload = Column(Text)  # сырые данные (JSON-строка, никогда не трогаем)
    scraped_at = Column(DateTime)

    # Координаты и адрес
    lat = Column(Float, CheckConstraint('lat >= -90 AND lat <= 90 AND lat IS NOT NULL'))  # валидация диапазона
    lng = Column(Float, CheckConstraint('lng >= -180 AND lng <= 180 AND lng IS NOT NULL'))  # валидация диапазона
    address = Column(Text, nullable=True)  # если доступно
    gmaps_place_id = Column(Text, nullable=True)  # если подтянем GMaps позже
    gmaps_url = Column(Text, nullable=True)  # можно хранить сразу, но допустимо генерировать на лету
    business_status = Column(Text, nullable=True)  # OPERATIONAL, CLOSED_TEMPORARILY, CLOSED_PERMANENTLY
    utc_offset_minutes = Column(Integer, nullable=True)  # UTC offset в минутах

    # Чистые поля (после нормализации)
    name = Column(Text)
    category = Column(Text)  # базовая рубрика (e.g., food, park, bar)
    description_full = Column(Text)  # полное очищенное описание
    summary = Column(Text)  # краткое саммари для карточек
    tags_csv = Column(Text)  # простые теги через запятую (thai,rooftop,romantic)
    price_level = Column(Integer, nullable=True)  # 0–4 (как в GMaps), если известен
    rating = Column(Float, nullable=True)  # рейтинг места (0.0-5.0)
    hours_json = Column(Text)  # JSON со временем работы (на будущее)
    picture_url = Column(Text, nullable=True)  # ссылка на главную фотографию места
    website = Column(Text, nullable=True)  # официальный сайт заведения
    phone = Column(Text, nullable=True)  # телефон заведения

    # Процесс/модерация
    processing_status = Column(Text, default="new")  # new | summarized | published | error
    last_error = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Отслеживание источника саммари
    summary_source = Column(Text, nullable=True)  # gpt | fallback
    summary_version = Column(Integer, default=1)  # версия саммари для перегенерации
    
    # AI Editor Agent поля
    ai_verified = Column(Text, nullable=True)  # true/false - проверен ли AI-агентом
    ai_verification_date = Column(DateTime, nullable=True)  # дата проверки AI-агентом
    ai_verification_data = Column(Text, nullable=True)  # JSON с результатами проверки
    
    # Interest Signals (новое поле для детекции активностей)
    interest_signals = Column(JSON, nullable=True)  # JSON с булевыми флагами активностей
    
    # Теневая схема протокола (Итерация 1)
    attempts = Column(Text, nullable=True, default='{}')  # JSON с попытками агентов
    quality_flags = Column(Text, nullable=True, default='{}')  # JSON с флагами качества
    
    # Bitset-теги для O(1) vibe_score (Netflix-style поиск)
    tag_bitset = Column(Integer, nullable=True, default=0)  # PostgreSQL INTEGER supports 64-bit
    category_id = Column(Integer, nullable=True)  # числовой ID категории для MMR
    sig_hash = Column(String(32), nullable=True)  # хэш для MMR диверсификации
    
    # Full-text search and signals
    search_vector = Column(TSVECTOR, nullable=True)  # PostgreSQL tsvector for full-text search
    signals = Column(JSON, nullable=True)  # JSON signals for surprise me feature
    
    def validate_coordinates(self) -> bool:
        """Validate coordinates are valid numbers (not NaN or infinite)"""
        if self.lat is None or self.lng is None:
            return False
        return not (math.isnan(self.lat) or math.isnan(self.lng) or 
                   math.isinf(self.lat) or math.isinf(self.lng))
    
    @classmethod
    def filter_valid_coordinates(cls, query):
        """Filter query to only include places with valid coordinates"""
        return query.filter(
            cls.lat.isnot(None),
            cls.lng.isnot(None),
            cls.lat >= -90,
            cls.lat <= 90,
            cls.lng >= -180,
            cls.lng <= 180
        )


class PlaceEvent(Base):
    """События места для теневой схемы протокола"""
    __tablename__ = "place_events"
    
    id = Column(Integer, primary_key=True, index=True)
    place_id = Column(Integer, ForeignKey('places.id', ondelete='CASCADE'), nullable=False)
    agent = Column(String(50), nullable=False)  # summarizer, enricher, editor, publisher
    code = Column(String(100), nullable=True)  # MISSING_COORDS, WEAK_SUMMARY, etc.
    level = Column(String(20), nullable=False)  # info, warn, error
    note = Column(Text, nullable=True)  # дополнительная информация
    ts = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    
    # Связь с местом
    place = relationship("Place", backref="events")
