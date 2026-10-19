from functools import lru_cache
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "EcoPulse AI"
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    secret_key: str = "dev-only-change-me"
    cors_origins: str = "http://localhost"

    postgres_user: str = "ecopulse"
    postgres_password: str = "ecopulse"
    postgres_db: str = "ecopulse"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    redis_url: str = "redis://localhost:6379/0"

    groq_api_key: str = ""
    gemini_api_key: str = ""
    openweather_api_key: str = ""
    cpcb_api_key: str = ""

    api_keys: str = ""  # comma-separated; empty = auth disabled (dev only)
    stations_json: str = ""
    artifacts_dir: str = "/app/artifacts"
    ingest_interval_seconds: int = 900
    drift_reference_days: int = 30
    drift_current_hours: int = 48
    drift_min_samples: int = 30
    drift_ks_alpha: float = 0.01
    drift_wasserstein_threshold: float = 0.25  # in units of reference std

    groq_model: str = "llama-3.3-70b-versatile"
    gemini_model: str = "gemini-2.0-flash"
    llm_timeout_seconds: int = 30
    rag_top_k: int = 4

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def stations(self) -> list["Station"]:
        import json

        from app.schemas.sensor import DEFAULT_STATIONS, Station

        if not self.stations_json.strip():
            return DEFAULT_STATIONS
        return [Station(**s) for s in json.loads(self.stations_json)]

    @property
    def api_key_list(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
