from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings with PostgreSQL-only database configuration."""
    
    # Database - PostgreSQL only (required)
    database_url: str = "postgresql+psycopg://ep:ep@localhost:5432/ep"
    
    # Security
    secret_key: str = "your-secret-key-here"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Admin
    admin_username: str = "admin"
    admin_email: str = "admin@example.com"
    admin_password: str = "admin123"
    admin_token: str = "admin-secret-token-change-in-production"
    
    # Google Maps - для разработки нужно настроить ограничения в Google Cloud Console
    google_maps_api_key: str = "AIzaSyBjExK9M7wOu929zQNbnlFJ8kjr-QreP6w"
    
    # OpenAI
    openai_api_key: str = ""
    
    # Environment
    environment: str = "development"
    
    # Search / config cache
    search_default_radius_m: int = 10_000
    config_cache_ttl_s: int = 300
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


settings = Settings()
