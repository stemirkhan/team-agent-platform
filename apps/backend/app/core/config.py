"""Application settings loaded from environment variables."""

import json
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for API, database, and local services."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Team Agent Platform API"
    app_env: str = "development"
    app_debug: bool = True
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg://team_agent_platform:team_agent_platform@localhost:5432/team_agent_platform"
    redis_url: str = "redis://localhost:6379/0"
    host_executor_base_url: str | None = None
    host_executor_timeout_seconds: float = 2.5
    host_executor_api_timeout_seconds: float = 15.0
    host_executor_workspace_command_timeout_seconds: float = 1800.0
    jwt_secret_key: str = "dev-secret-key-change-me-at-least-32-chars"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://[::1]:3000",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: list[str] | str) -> list[str]:
        """Accept JSON arrays, comma-separated strings, or native lists from env."""
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            normalized = value.strip()
            if normalized.startswith("["):
                try:
                    parsed = json.loads(normalized)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    return [
                        str(item).strip()
                        for item in parsed
                        if isinstance(item, str) and item.strip()
                    ]
            return [
                item.strip().strip("\"").strip("'")
                for item in normalized.split(",")
                if item.strip().strip("\"").strip("'")
            ]
        return []


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
