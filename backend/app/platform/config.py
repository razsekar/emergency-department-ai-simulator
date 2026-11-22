"""Application settings, loaded from environment variables (never from frontend code)."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "ED Patient Flow Simulator"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://edsim:edsim@db:5432/edsim"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:4200"])
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
