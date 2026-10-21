import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Configurazione letta solo da variabili d'ambiente (mai dal repository)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = Field(default="development", pattern="^(development|test|production)$")
    database_url: SecretStr | None = None
    twelve_data_api_key: SecretStr | None = None
    finnhub_api_key: SecretStr | None = None
    reddit_client_id: SecretStr | None = None
    reddit_client_secret: SecretStr | None = None
    # Accetta JSON (["https://a.app"]) oppure un elenco separato da virgole.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    cache_dir: Path = Path(".cache")
    # Tasso annuo usato per il costo di finanziamento degli ETF a leva sintetici.
    funding_rate: float = Field(default=0.04, ge=0, le=0.2)
    # Gestione del rischio (uso personale, capitale 500-2.000 euro).
    capital_eur: float = Field(default=1000.0, ge=500, le=2000)
    risk_per_trade: float = Field(default=0.01, gt=0, le=0.01)
    max_daily_loss: float = Field(default=0.03, gt=0, le=0.03)
    max_open_positions: int = Field(default=3, ge=1, le=3)
    max_lev3_exposure: float = Field(default=0.30, gt=0, le=0.30)
    max_correlation: float = Field(default=0.80, gt=0, le=1)
    min_order_eur: float = Field(default=10.0, ge=1)
    # Notifiche delle nuove proposte (facoltative) con ntfy.sh: argomento privato.
    ntfy_topic: SecretStr | None = None
    # Segreto condiviso con il frontend: senza, in produzione l'API rifiuta ogni richiesta.
    api_shared_secret: SecretStr | None = None
    # Trading 212 (Fase 5, passo B: sola lettura del conto Invest).
    t212_api_key: SecretStr | None = None
    t212_api_secret: SecretStr | None = None
    t212_env: str = Field(default="live", pattern="^(live|demo)$")
    # Passo C: ordini. Disattivati di default; "demo" usa il conto di prova, "live" quello reale.
    # La chiave per gli ordini è separata da quella di sola lettura.
    orders_mode: str = Field(default="disabled", pattern="^(disabled|demo|live)$")
    t212_order_api_key: SecretStr | None = None
    t212_order_api_secret: SecretStr | None = None
    # Limiti rigidi per ordine e per giorno, oltre a quelli di rischio.
    max_order_eur: float = Field(default=200.0, ge=10, le=2000)
    max_orders_per_day: int = Field(default=3, ge=1, le=10)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            items = json.loads(text) if text.startswith("[") else text.split(",")
            if not isinstance(items, list):
                raise ValueError("CORS_ORIGINS non valido")
            value = items
        if isinstance(value, list):
            # Un'origine non ha mai lo slash finale: lo si toglie per evitare errori di copia.
            return [str(v).strip().rstrip("/") for v in value if str(v).strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
