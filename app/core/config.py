from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Anti-Detect Scraping Proxy API"
    app_version: str = "2.0.0"
    api_prefix: str = "/api/v1"
    enable_docs: bool = True

    default_impersonate: str = "chrome120"
    request_timeout_seconds: float = Field(default=30.0, gt=0.0, le=300.0)
    max_response_bytes: int = Field(default=10_485_760, gt=0, le=104_857_600)
    session_max_clients: int = Field(default=64, gt=0, le=1024)
    follow_redirects: bool = True
    verify_tls: bool = True

    cors_origins: list[str] = ["*"]
    cors_methods: list[str] = ["GET", "POST", "OPTIONS"]
    cors_headers: list[str] = ["*"]
    cors_allow_credentials: bool = False

    log_level: str = "INFO"

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith("/"):
            value = f"/{value}"
        return value.rstrip("/") or "/"

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        valid = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
        if normalized not in valid:
            allowed = ", ".join(sorted(valid))
            raise ValueError(f"log_level must be one of: {allowed}")
        return normalized


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
