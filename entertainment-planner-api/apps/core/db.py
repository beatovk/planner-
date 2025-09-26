from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings
import os
import logging

logger = logging.getLogger(__name__)


def resolve_database_url() -> str:
    """
    Resolve database URL with PostgreSQL-only validation.
    
    Priority:
    1. ENV: DATABASE_URL
    2. settings.database_url (from .env or config.py)
    
    Raises:
        RuntimeError: If DATABASE_URL is not set or not PostgreSQL
    """
    url = os.getenv("DATABASE_URL") or settings.database_url
    if not url:
        raise RuntimeError(
            "DATABASE_URL is required and must point to PostgreSQL "
            "(e.g. postgresql+psycopg://user:pass@host:5432/db)"
        )
    
    if not (url.startswith("postgresql://") or url.startswith("postgresql+psycopg://")):
        raise RuntimeError(
            f"Postgres-only mode: unsupported DATABASE_URL '{url}'. "
            "Expected 'postgresql+psycopg://...'."
        )
    
    return url


def _mask_dsn(url: str) -> str:
    """Mask sensitive information in database URL for logging."""
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        if "@" in rest and ":" in rest.split("@", 1)[0]:
            creds, hostpart = rest.split("@", 1)
            user = creds.split(":", 1)[0]
            return f"{scheme}://{user}:***@{hostpart}"
    return url


# Resolve database URL
DB_URL = resolve_database_url()
logger.info("DB init: %s", _mask_dsn(DB_URL))

# Create PostgreSQL engine with proper connection pooling
engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    future=True,
    pool_size=5,          # подстрой под нагрузку
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,    # раз в 30 мин обновлять соединения
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
