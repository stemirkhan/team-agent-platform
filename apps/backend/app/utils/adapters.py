"""Helpers for runtime-specific export artifacts."""

import json
import re
from typing import Any

_DEFAULT_CODEX_REASONING = "medium"
_DEFAULT_CODEX_SANDBOX = "workspace-write"
_DEFAULT_CODEX_INSTRUCTIONS = "Follow task instructions and use available tools."
_DEFAULT_CLAUDE_MODEL = "inherit"
_DEFAULT_CLAUDE_PERMISSION_MODE = "default"
_DEFAULT_OPENCODE_PERMISSION = "ask"


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
        codex_profile = (
            item.get("codex")
            if isinstance(item.get("codex"), dict)
            else {}
        )
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


def render_claude_agent_markdown(claude_profile: dict[str, Any]) -> str:
    """Render one Claude Code agent file in Markdown with YAML frontmatter."""
    normalized = _normalize_claude_profile(claude_profile)
    lines = [
        "---",
        f"name: {_yaml_string(normalized['name'])}",
        f"description: {_yaml_string(normalized['description'])}",
        f"model: {_yaml_string(normalized['model'])}",
        f"permissionMode: {_yaml_string(normalized['permission_mode'])}",
        "---",
        "",
        normalized["prompt"],
    ]
    return "\n".join(lines).strip() + "\n"


def build_claude_team_files(team_items: list[dict[str, Any]]) -> dict[str, str]:
    """Build minimal Claude Code team bundle files."""
    files: dict[str, str] = {}
    used_keys: set[str] = set()

    for index, item in enumerate(team_items, start=1):
        base_key = _slugify_key(
            str(item.get("role_name") or item.get("agent_slug") or f"agent-{index}")
        )
        if not base_key:
            base_key = f"agent-{index}"
        key = _make_unique_key(base_key=base_key, used_keys=used_keys)

        claude_profile = item.get("claude") if isinstance(item.get("claude"), dict) else {}
        profile = dict(claude_profile)
        profile.setdefault("name", key)
        files[f".claude/agents/{key}.md"] = render_claude_agent_markdown(profile)

    return files


def render_opencode_agent_markdown(opencode_profile: dict[str, Any]) -> str:
    """Render one OpenCode agent file in Markdown with YAML frontmatter."""
    normalized = _normalize_opencode_profile(opencode_profile)
    lines = [
        "---",
        f"description: {_yaml_string(normalized['description'])}",
        'mode: "subagent"',
    ]
    if normalized["model"]:
        lines.append(f"model: {_yaml_string(normalized['model'])}")
    lines.append(f"permission: {_yaml_string(normalized['permission'])}")
    lines.extend(
        [
            "---",
            "",
            normalized["prompt"],
        ]
    )
    return "\n".join(lines).strip() + "\n"


def build_opencode_team_files(team_items: list[dict[str, Any]]) -> dict[str, str]:
    """Build minimal OpenCode team bundle files."""
    files: dict[str, str] = {}
    used_keys: set[str] = set()

    for index, item in enumerate(team_items, start=1):
        base_key = _slugify_key(
            str(item.get("role_name") or item.get("agent_slug") or f"agent-{index}")
        )
        if not base_key:
            base_key = f"agent-{index}"
        key = _make_unique_key(base_key=base_key, used_keys=used_keys)

        opencode_profile = item.get("opencode") if isinstance(item.get("opencode"), dict) else {}
        files[f".opencode/agents/{key}.md"] = render_opencode_agent_markdown(opencode_profile)

    return files


def _normalize_codex_profile(codex_profile: dict[str, Any]) -> dict[str, str | None]:
    """Return stable codex config values used in TOML generation."""
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


def _normalize_claude_profile(claude_profile: dict[str, Any]) -> dict[str, str]:
    """Return stable Claude Code config values used in Markdown generation."""
    name = _slugify_key(_normalize_str(claude_profile.get("name")) or "agent")
    if not name:
        name = "agent"
    description = _normalize_str(claude_profile.get("description")) or "Agent role"
    model = _normalize_str(claude_profile.get("model")) or _DEFAULT_CLAUDE_MODEL
    permission_mode = (
        _normalize_str(claude_profile.get("permission_mode")) or _DEFAULT_CLAUDE_PERMISSION_MODE
    )
    prompt = _normalize_str(claude_profile.get("prompt")) or _DEFAULT_CODEX_INSTRUCTIONS
    return {
        "name": name,
        "description": description,
        "model": model,
        "permission_mode": permission_mode,
        "prompt": prompt,
    }


def _normalize_opencode_profile(opencode_profile: dict[str, Any]) -> dict[str, str]:
    """Return stable OpenCode config values used in Markdown generation."""
    description = _normalize_str(opencode_profile.get("description")) or "Agent role"
    model = _normalize_str(opencode_profile.get("model")) or ""
    permission = (
        _normalize_str(opencode_profile.get("permission")) or _DEFAULT_OPENCODE_PERMISSION
    )
    prompt = _normalize_str(opencode_profile.get("prompt")) or _DEFAULT_CODEX_INSTRUCTIONS
    return {
        "description": description,
        "model": model,
        "permission": permission,
        "prompt": prompt,
    }


def _toml_string(value: str) -> str:
    """Return TOML-safe basic string."""
    return json.dumps(value, ensure_ascii=False)


def _yaml_string(value: str) -> str:
    """Return YAML-safe string value."""
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
