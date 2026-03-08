"""Helpers for agent profile markdown files and skills."""

import re
from pathlib import PurePosixPath
from typing import Any

_SKILL_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
_RESERVED_MARKDOWN_ROOTS = {".codex", ".claude", ".opencode", "skills"}


def normalize_skill_records(value: Any, *, strict: bool) -> list[dict[str, str]]:
    """Normalize raw skill payloads into deterministic dictionaries."""
    if value is None:
        return []
    if not isinstance(value, list):
        return _raise_or_empty("Skills must be a list.", strict=strict)

    normalized_records: list[dict[str, str]] = []
    seen_slugs: set[str] = set()

    for item in value:
        if not isinstance(item, dict):
            return _raise_or_empty("Each skill must be an object.", strict=strict)

        try:
            slug = normalize_skill_slug(item.get("slug"))
            content = normalize_markdown_content(item.get("content"), label=f"Skill '{slug}'")
            description = normalize_optional_text(item.get("description"))
        except ValueError as exc:
            return _raise_or_empty(str(exc), strict=strict)

        if slug in seen_slugs:
            return _raise_or_empty(f"Duplicate skill slug '{slug}'.", strict=strict)

        seen_slugs.add(slug)
        record = {"slug": slug, "content": content}
        if description:
            record["description"] = description
        normalized_records.append(record)

    return normalized_records


def normalize_markdown_file_records(value: Any, *, strict: bool) -> list[dict[str, str]]:
    """Normalize raw markdown file payloads into deterministic dictionaries."""
    if value is None:
        return []
    if not isinstance(value, list):
        return _raise_or_empty("Markdown files must be a list.", strict=strict)

    normalized_records: list[dict[str, str]] = []
    seen_paths: set[str] = set()

    for item in value:
        if not isinstance(item, dict):
            return _raise_or_empty("Each markdown file must be an object.", strict=strict)

        try:
            path = normalize_markdown_path(item.get("path"))
            content = normalize_markdown_content(
                item.get("content"),
                label=f"Markdown file '{path}'",
            )
        except ValueError as exc:
            return _raise_or_empty(str(exc), strict=strict)

        if path in seen_paths:
            return _raise_or_empty(
                f"Duplicate markdown file path '{path}'.",
                strict=strict,
            )

        seen_paths.add(path)
        normalized_records.append({"path": path, "content": content})

    return normalized_records


def merge_manifest_assets(
    *,
    manifest: dict[str, Any] | None,
    skills: list[dict[str, str]],
    markdown_files: list[dict[str, str]],
) -> dict[str, Any] | None:
    """Return manifest payload with normalized skills and markdown files."""
    normalized_manifest = dict(manifest) if isinstance(manifest, dict) else {}

    if skills:
        normalized_manifest["skills"] = skills
    else:
        normalized_manifest.pop("skills", None)

    if markdown_files:
        normalized_manifest["markdown_files"] = markdown_files
    else:
        normalized_manifest.pop("markdown_files", None)

    return normalized_manifest or None


def normalize_skill_slug(value: Any) -> str:
    """Validate skill slug format."""
    if not isinstance(value, str):
        raise ValueError("Skill slug is required.")

    normalized = value.strip().lower()
    if not _SKILL_SLUG_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Skill slug must use 2-64 lowercase characters, digits, hyphen, or underscore."
        )
    return normalized


def normalize_markdown_path(value: Any) -> str:
    """Validate exportable markdown path."""
    if not isinstance(value, str):
        raise ValueError("Markdown file path is required.")

    normalized = value.strip().replace("\\", "/")
    if not normalized:
        raise ValueError("Markdown file path is required.")
    if normalized.startswith("/"):
        raise ValueError("Markdown file path must be relative.")

    path = PurePosixPath(normalized)
    parts = path.parts
    if not parts:
        raise ValueError("Markdown file path is required.")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Markdown file path must not contain '.' or '..' segments.")
    if parts[0] in _RESERVED_MARKDOWN_ROOTS:
        raise ValueError(
            "Markdown file path must not target reserved export directories "
            "('.codex', '.claude', '.opencode', 'skills')."
        )

    normalized_path = str(path)
    if not normalized_path.lower().endswith(".md"):
        raise ValueError("Only .md files are supported.")
    return normalized_path


def normalize_markdown_content(value: Any, *, label: str) -> str:
    """Validate markdown body content."""
    if not isinstance(value, str):
        raise ValueError(f"{label} content is required.")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} content is required.")
    return normalized


def normalize_optional_text(value: Any) -> str | None:
    """Return stripped string when available."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _raise_or_empty(message: str, *, strict: bool) -> list[dict[str, str]]:
    """Raise validation error in strict mode or drop malformed records otherwise."""
    if strict:
        raise ValueError(message)
    return []
