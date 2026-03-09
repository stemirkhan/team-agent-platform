"""Configuration for the local host executor bridge."""

import json
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the host executor bridge."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Team Agent Platform Host Executor"
    app_env: str = "development"
    app_debug: bool = True
    host_executor_host: str = "0.0.0.0"
    host_executor_port: int = 8765
    workspace_root: str = "~/.team-agent-platform/workspaces"
    workspace_command_timeout_seconds: int = 1800
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
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
