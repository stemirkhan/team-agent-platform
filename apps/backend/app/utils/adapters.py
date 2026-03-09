"""Helpers for Codex export artifacts."""

import json
import re
from typing import Any

_DEFAULT_CODEX_REASONING = "medium"
_DEFAULT_CODEX_SANDBOX = "workspace-write"
_DEFAULT_CODEX_INSTRUCTIONS = "Follow task instructions and use available tools."


def render_codex_agent_toml(codex_profile: dict[str, Any]) -> str:
    """Render one agent role config in TOML format."""
    normalized = _normalize_codex_profile(codex_profile)
    lines = [
        f"description = {_toml_string(normalized['description'])}",
        f"model_reasoning_effort = {_toml_string(normalized['model_reasoning_effort'])}",
        f"sandbox_mode = {_toml_string(normalized['sandbox_mode'])}",
        f"developer_instructions = {_toml_string(normalized['developer_instructions'])}",
    ]
    if normalized["model"]:
        lines.insert(1, f"model = {_toml_string(normalized['model'])}")
    return "\n".join(lines).strip() + "\n"


def build_codex_team_files(team_items: list[dict[str, Any]]) -> dict[str, str]:
    """Build minimal Codex team bundle files."""
    files: dict[str, str] = {}
    config_lines = [
        "[features]",
        "multi_agent = true",
    ]
    used_keys: set[str] = set()

    for index, item in enumerate(team_items, start=1):
        base_key = _slugify_key(
            str(item.get("role_name") or item.get("agent_slug") or f"agent-{index}")
        )
        if not base_key:
            base_key = f"agent-{index}"
        key = _make_unique_key(base_key=base_key, used_keys=used_keys)

        role_name = str(item.get("role_name") or key)
        codex_profile = item.get("codex") if isinstance(item.get("codex"), dict) else {}
        role_description = _build_codex_team_role_description(
            item=item,
            role_name=role_name,
            codex_profile=codex_profile,
        )
        files[f".codex/agents/{key}.toml"] = render_codex_agent_toml(codex_profile)

        config_lines.extend(
            [
                "",
                f"[agents.{_toml_string(key)}]",
                f"description = {_toml_string(role_description)}",
                f"config_file = {_toml_string(f'agents/{key}.toml')}",
            ]
        )

    files[".codex/config.toml"] = "\n".join(config_lines).strip() + "\n"
    return files


def _normalize_codex_profile(codex_profile: dict[str, Any]) -> dict[str, str | None]:
    """Return stable Codex config values used in TOML generation."""
    description = _normalize_str(codex_profile.get("description")) or "Agent role"
    model = _normalize_str(codex_profile.get("model"))
    reasoning = (
        _normalize_str(codex_profile.get("model_reasoning_effort"))
        or _DEFAULT_CODEX_REASONING
    )
    sandbox = _normalize_str(codex_profile.get("sandbox_mode")) or _DEFAULT_CODEX_SANDBOX
    developer_instructions = (
        _normalize_str(codex_profile.get("developer_instructions"))
        or _DEFAULT_CODEX_INSTRUCTIONS
    )
    return {
        "description": description,
        "model": model,
        "model_reasoning_effort": reasoning,
        "sandbox_mode": sandbox,
        "developer_instructions": developer_instructions,
    }


def _toml_string(value: str) -> str:
    """Return TOML-safe basic string."""
    return json.dumps(value, ensure_ascii=False)


def _slugify_key(value: str) -> str:
    """Convert arbitrary role label into a stable key."""
    return re.sub(r"[^a-z0-9_-]+", "-", value.lower()).strip("-")


def _make_unique_key(*, base_key: str, used_keys: set[str]) -> str:
    """Ensure config key uniqueness by suffixing duplicates."""
    key = base_key
    suffix = 2
    while key in used_keys:
        key = f"{base_key}-{suffix}"
        suffix += 1
    used_keys.add(key)
    return key


def _normalize_str(value: Any) -> str | None:
    """Normalize value to stripped string when available."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _build_codex_team_role_description(
    *,
    item: dict[str, Any],
    role_name: str,
    codex_profile: dict[str, Any],
) -> str:
    """Build human-readable Codex team role description for config.toml."""
    explicit_description = _normalize_str(item.get("config_description"))
    if explicit_description:
        return explicit_description

    agent_title = _normalize_str(item.get("agent_title"))
    agent_short_description = _normalize_str(item.get("agent_short_description"))
    codex_description = _normalize_str(codex_profile.get("description"))
    description_source = agent_short_description or codex_description or agent_title or role_name

    if agent_title and description_source and description_source != agent_title:
        return f"{agent_title}: {description_source}"
    return description_source
