from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://inventory_app:change_me@localhost:5432/inventory",
        alias="DATABASE_URL",
    )
    api_key: str = Field(default="replace-with-a-long-random-key", alias="API_KEY")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    forecast_horizon_days: int = Field(default=90, alias="FORECAST_HORIZON_DAYS", ge=1, le=365)
    min_training_days: int = Field(default=90, alias="MIN_TRAINING_DAYS", ge=28, le=1000)
    default_service_level: float = Field(default=0.95, alias="DEFAULT_SERVICE_LEVEL", gt=0.5, lt=0.9999)
    pipeline_poll_seconds: int = Field(default=15, alias="PIPELINE_POLL_SECONDS", ge=2, le=3600)
    job_heartbeat_seconds: int = Field(default=30, alias="JOB_HEARTBEAT_SECONDS", ge=5, le=300)
    job_stale_minutes: int = Field(default=30, alias="JOB_STALE_MINUTES", ge=2, le=1440)
    external_api_allowed_hosts: str = Field(default="api.open-meteo.com", alias="EXTERNAL_API_ALLOWED_HOSTS")
    allowed_ingestion_roots: str = Field(default="/app/sample_data,/app/runtime", alias="ALLOWED_INGESTION_ROOTS")

    @property
    def external_api_hosts(self) -> list[str]:
        return [item.strip().lower() for item in self.external_api_allowed_hosts.split(",") if item.strip()]

    @property
    def ingestion_roots(self) -> list[str]:
        return [item.strip() for item in self.allowed_ingestion_roots.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
