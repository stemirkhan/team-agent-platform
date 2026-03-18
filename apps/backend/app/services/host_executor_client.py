"""Shared helpers for backend-to-host-executor HTTP calls."""

from __future__ import annotations

from app.core.config import Settings

HOST_EXECUTOR_SECRET_HEADER = "X-TAP-Executor-Secret"


def build_host_executor_headers(
    settings: Settings,
    *,
    include_json_content_type: bool = False,
) -> dict[str, str]:
    """Return normalized HTTP headers for host executor requests."""
    headers = {
        "Accept": "application/json",
        HOST_EXECUTOR_SECRET_HEADER: settings.host_executor_shared_secret,
    }
    if include_json_content_type:
        headers["Content-Type"] = "application/json"
    return headers


def normalize_host_executor_base_url(value: str | None) -> str | None:
    """Normalize optional host executor base URL configuration."""
    if value is None:
        return None
    normalized = value.strip().rstrip("/")
    return normalized or None
