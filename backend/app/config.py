from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurazione letta solo da variabili d'ambiente (mai dal repository)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = Field(default="development", pattern="^(development|test|production)$")
    database_url: SecretStr | None = None
    twelve_data_api_key: SecretStr | None = None
    finnhub_api_key: SecretStr | None = None
    reddit_client_id: SecretStr | None = None
    reddit_client_secret: SecretStr | None = None
    cors_origins: list[str] = ["http://localhost:3000"]
    cache_dir: Path = Path(".cache")
    # Tasso annuo usato per il costo di finanziamento degli ETF a leva sintetici.
    funding_rate: float = Field(default=0.04, ge=0, le=0.2)


@lru_cache
def get_settings() -> Settings:
    return Settings()
