"""Business logic for agent and team exports."""

import json
from io import BytesIO
from typing import Any
from urllib.parse import urlencode
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import HTTPException, status

from app.models.agent import AgentStatus
from app.models.agent_version import AgentVersion
from app.models.export_job import ExportEntityType, ExportStatus, RuntimeTarget
from app.models.team import TeamItem, TeamStatus
from app.models.user import User
from app.repositories.agent import AgentRepository
from app.repositories.agent_version import AgentVersionRepository
from app.repositories.export_job import ExportJobRepository
from app.repositories.team import TeamRepository
from app.schemas.export import (
    ClaudeExportOptions,
    CodexExportOptions,
    ExportCreate,
    ExportListResponse,
    OpenCodeExportOptions,
)
from app.utils.adapters import (
    build_claude_team_files,
    build_codex_team_files,
    build_opencode_team_files,
    render_claude_agent_markdown,
    render_codex_agent_toml,
    render_opencode_agent_markdown,
)
from app.utils.agent_assets import normalize_markdown_file_records, normalize_skill_records


class ExportService:
    """Use-case orchestration for export jobs."""

    _DEFAULT_REASONING_EFFORT = "medium"
    _DEFAULT_SANDBOX_MODE = "workspace-write"
    _DEFAULT_CLAUDE_MODEL = "inherit"
    _DEFAULT_CLAUDE_PERMISSION_MODE = "default"
    _DEFAULT_OPENCODE_PERMISSION = "ask"
    _DEFAULT_INSTRUCTIONS = "Follow task instructions and use available tools."

    def __init__(
        self,
        export_repository: ExportJobRepository,
        agent_repository: AgentRepository,
        agent_version_repository: AgentVersionRepository,
        team_repository: TeamRepository,
    ) -> None:
        self.export_repository = export_repository
        self.agent_repository = agent_repository
        self.agent_version_repository = agent_version_repository
        self.team_repository = team_repository

    def create_agent_export(self, *, slug: str, payload: ExportCreate, current_user: User):
        """Create export job for published agent."""
        self._ensure_supported_runtime(payload.runtime_target.value)

        agent = self.agent_repository.get_by_slug(slug)
        if agent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
        if agent.status != AgentStatus.PUBLISHED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only published agents can be exported.",
            )
        artifact_payload = self._build_agent_payload(
            agent=agent,
            runtime_target=payload.runtime_target.value,
            codex_options=payload.codex,
            claude_options=payload.claude,
            opencode_options=payload.opencode,
        )

        return self.export_repository.create(
            entity_type=ExportEntityType.AGENT.value,
            entity_id=agent.id,
            runtime_target=payload.runtime_target.value,
            status=ExportStatus.COMPLETED.value,
            result_url=self._build_result_url(
                entity_type=ExportEntityType.AGENT.value,
                slug=slug,
                runtime_target=payload.runtime_target.value,
                codex_options=payload.codex,
                claude_options=payload.claude,
                opencode_options=payload.opencode,
                bundle_assets=self._should_archive_agent_payload(artifact_payload),
            ),
            error_message=None,
            created_by=current_user.id,
        )

    def create_team_export(self, *, slug: str, payload: ExportCreate, current_user: User):
        """Create export job for published non-empty team."""
        self._ensure_supported_runtime(payload.runtime_target.value)

        team = self.team_repository.get_by_slug(slug)
        if team is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")
        if team.status != TeamStatus.PUBLISHED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only published teams can be exported.",
            )

        items = self.team_repository.list_item_entities(team.id)
        if not items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot export empty team.",
            )
        self._build_team_payload(
            team=team,
            items=items,
            runtime_target=payload.runtime_target.value,
            codex_options=payload.codex,
            claude_options=payload.claude,
            opencode_options=payload.opencode,
        )

        return self.export_repository.create(
            entity_type=ExportEntityType.TEAM.value,
            entity_id=team.id,
            runtime_target=payload.runtime_target.value,
            status=ExportStatus.COMPLETED.value,
            result_url=self._build_result_url(
                entity_type=ExportEntityType.TEAM.value,
                slug=slug,
                runtime_target=payload.runtime_target.value,
                codex_options=payload.codex,
                claude_options=payload.claude,
                opencode_options=payload.opencode,
            ),
            error_message=None,
            created_by=current_user.id,
        )

    def get_export(self, *, export_id: UUID, current_user: User):
        """Return export job if current user is creator."""
        job = self.export_repository.get_by_id(export_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Export job not found.",
            )
        if job.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the export creator can access this job.",
            )
        return job

    def list_agent_exports(
        self,
        *,
        slug: str,
        current_user: User,
        limit: int,
        offset: int,
    ) -> ExportListResponse:
        """Return export jobs for one agent owned by current user."""
        agent = self.agent_repository.get_by_slug(slug)
        if agent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")

        items, total = self.export_repository.list_for_creator_entity(
            created_by=current_user.id,
            entity_type=ExportEntityType.AGENT.value,
            entity_id=agent.id,
            limit=limit,
            offset=offset,
        )
        return ExportListResponse(items=items, total=total, limit=limit, offset=offset)

    def list_team_exports(
        self,
        *,
        slug: str,
        current_user: User,
        limit: int,
        offset: int,
    ) -> ExportListResponse:
        """Return export jobs for one team owned by current user."""
        team = self.team_repository.get_by_slug(slug)
        if team is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")

        items, total = self.export_repository.list_for_creator_entity(
            created_by=current_user.id,
            entity_type=ExportEntityType.TEAM.value,
            entity_id=team.id,
            limit=limit,
            offset=offset,
        )
        return ExportListResponse(items=items, total=total, limit=limit, offset=offset)

    def build_download_artifact(
        self,
        *,
        entity_type: ExportEntityType,
        slug: str,
        runtime_target: str,
        codex_options: CodexExportOptions | None = None,
        claude_options: ClaudeExportOptions | None = None,
        opencode_options: OpenCodeExportOptions | None = None,
    ) -> tuple[str, bytes, str]:
        """Build artifact content for a published export target."""
        self._ensure_supported_runtime(runtime_target)

        if entity_type == ExportEntityType.AGENT:
            entity = self.agent_repository.get_by_slug(slug)
            if entity is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Agent not found.",
                )
            if entity.status != AgentStatus.PUBLISHED.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only published agents can be downloaded.",
                )
            payload = self._build_agent_payload(
                agent=entity,
                runtime_target=runtime_target,
                codex_options=codex_options,
                claude_options=claude_options,
                opencode_options=opencode_options,
            )
            if self._should_archive_agent_payload(payload):
                files = self._build_agent_bundle_files(
                    payload=payload,
                    runtime_target=runtime_target,
                )
                buffer = BytesIO()
                with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
                    for path, content in files.items():
                        archive.writestr(path, content)

                filename = f"{slug}-{runtime_target}.zip"
                return filename, buffer.getvalue(), "application/zip"

            if runtime_target == RuntimeTarget.CODEX.value:
                content = render_codex_agent_toml(payload["codex"]).encode("utf-8")
                filename = f"{slug}.toml"
                media_type = "text/plain; charset=utf-8"
            elif runtime_target == RuntimeTarget.CLAUDE_CODE.value:
                content = render_claude_agent_markdown(payload["claude"]).encode("utf-8")
                filename = f"{slug}.md"
                media_type = "text/markdown; charset=utf-8"
            else:
                content = render_opencode_agent_markdown(payload["opencode"]).encode("utf-8")
                filename = f"{slug}.md"
                media_type = "text/markdown; charset=utf-8"
            return filename, content, media_type

        entity = self.team_repository.get_by_slug(slug)
        if entity is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")
        if entity.status != TeamStatus.PUBLISHED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only published teams can be downloaded.",
            )

        items = self.team_repository.list_item_entities(entity.id)
        payload = self._build_team_payload(
            team=entity,
            items=items,
            runtime_target=runtime_target,
            codex_options=codex_options,
            claude_options=claude_options,
            opencode_options=opencode_options,
        )
        if runtime_target == RuntimeTarget.CODEX.value:
            files = build_codex_team_files(payload["team_items"])
        elif runtime_target == RuntimeTarget.CLAUDE_CODE.value:
            files = build_claude_team_files(payload["team_items"])
        else:
            files = build_opencode_team_files(payload["team_items"])
        self._append_team_asset_files(
            files=files,
            team_items=payload["team_items"],
            runtime_target=runtime_target,
        )

        buffer = BytesIO()
        with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
            for path, content in files.items():
                archive.writestr(path, content)

        filename = f"{slug}-{runtime_target}.zip"
        return filename, buffer.getvalue(), "application/zip"

    def _build_agent_payload(
        self,
        *,
        agent,
        runtime_target: str,
        codex_options: CodexExportOptions | None = None,
        claude_options: ClaudeExportOptions | None = None,
        opencode_options: OpenCodeExportOptions | None = None,
    ) -> dict[str, Any]:
        """Build canonical payload for single-agent export."""
        current_profile = self._ensure_runtime_supported_for_agent(
            agent=agent,
            runtime_target=runtime_target,
        )
        manifest = self._extract_manifest(current_profile)

        description = self._first_non_empty_str(
            manifest.get("description"),
            agent.full_description,
            agent.short_description,
            default="No description.",
        )
        instructions = self._first_non_empty_str(
            manifest.get("instructions"),
            current_profile.install_instructions,
            description,
            default=self._DEFAULT_INSTRUCTIONS,
        )
        codex_profile = self._build_codex_profile(
            agent=agent,
            manifest=manifest,
            fallback_description=description,
            fallback_instructions=instructions,
            codex_options=codex_options,
        )
        claude_profile = self._build_claude_profile(
            agent=agent,
            manifest=manifest,
            fallback_name=agent.slug,
            fallback_description=description,
            fallback_prompt=instructions,
            claude_options=claude_options,
        )
        opencode_profile = self._build_opencode_profile(
            agent=agent,
            manifest=manifest,
            fallback_description=description,
            fallback_prompt=instructions,
            opencode_options=opencode_options,
        )

        payload = {
            "entity_type": ExportEntityType.AGENT.value,
            "slug": agent.slug,
            "title": agent.title,
            "description": description,
            "runtime_target": runtime_target,
            "entrypoints": self._as_str_list(manifest.get("entrypoints")),
            "instructions": instructions,
            "tools_required": self._as_str_list(manifest.get("tools_required")),
            "permissions_required": self._as_str_list(manifest.get("permissions_required")),
            "tags": self._as_str_list(manifest.get("tags")),
            "skills": self._extract_skill_records(manifest),
            "markdown_files": self._extract_markdown_file_records(manifest),
            "codex": codex_profile,
            "claude": claude_profile,
            "opencode": opencode_profile,
        }
        return payload

    def _build_team_payload(
        self,
        *,
        team,
        items: list[TeamItem],
        runtime_target: str,
        codex_options: CodexExportOptions | None = None,
        claude_options: ClaudeExportOptions | None = None,
        opencode_options: OpenCodeExportOptions | None = None,
    ) -> dict[str, Any]:
        """Build canonical payload for team export."""
        if not items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot export empty team.",
            )

        team_items: list[dict[str, Any]] = []
        tools_required: set[str] = set()
        permissions_required: set[str] = set()
        tags: set[str] = set()

        for item in items:
            current_profile = item.agent_version
            if current_profile is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Team item agent profile not found.",
                )
            agent = current_profile.agent
            if agent is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Team item agent not found.",
                )
            if agent.status != AgentStatus.PUBLISHED.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Agent '{agent.slug}' must be published for export.",
                )

            validated_profile = self._ensure_runtime_supported_for_version(
                agent=agent,
                version=current_profile,
                runtime_target=runtime_target,
            )
            manifest = self._extract_manifest(validated_profile)

            description = self._first_non_empty_str(
                manifest.get("description"),
                agent.short_description,
                default=f"{item.role_name} role for team '{team.slug}'.",
            )
            instructions = self._first_non_empty_str(
                manifest.get("instructions"),
                validated_profile.install_instructions,
                default=self._DEFAULT_INSTRUCTIONS,
            )

            codex_profile = self._build_codex_profile(
                agent=agent,
                manifest=manifest,
                fallback_description=description,
                fallback_instructions=instructions,
                codex_options=codex_options,
            )
            claude_profile = self._build_claude_profile(
                agent=agent,
                manifest=manifest,
                fallback_name=item.role_name or agent.slug,
                fallback_description=description,
                fallback_prompt=instructions,
                claude_options=claude_options,
            )
            opencode_profile = self._build_opencode_profile(
                agent=agent,
                manifest=manifest,
                fallback_description=description,
                fallback_prompt=instructions,
                opencode_options=opencode_options,
            )

            tools_required.update(self._as_str_list(manifest.get("tools_required")))
            permissions_required.update(self._as_str_list(manifest.get("permissions_required")))
            tags.update(self._as_str_list(manifest.get("tags")))

            team_items.append(
                {
                    "agent_slug": agent.slug,
                    "agent_title": agent.title,
                    "agent_short_description": agent.short_description,
                    "role_name": item.role_name,
                    "order_index": item.order_index,
                    "is_required": item.is_required,
                    "skills": self._extract_skill_records(manifest),
                    "markdown_files": self._extract_markdown_file_records(manifest),
                    "codex": codex_profile,
                    "claude": claude_profile,
                    "opencode": opencode_profile,
                }
            )

        payload = {
            "entity_type": ExportEntityType.TEAM.value,
            "slug": team.slug,
            "title": team.title,
            "description": str(team.description or "No description."),
            "runtime_target": runtime_target,
            "entrypoints": [],
            "instructions": "Run agents in order_index order with required roles first.",
            "tools_required": sorted(tools_required),
            "permissions_required": sorted(permissions_required),
            "tags": sorted(tags),
            "team_items": team_items,
        }
        return payload

    def _ensure_runtime_supported_for_agent(
        self,
        *,
        agent,
        runtime_target: str,
    ) -> AgentVersion:
        """Validate current agent export profile and return it when present."""
        current_profile = self.agent_version_repository.get_latest_for_agent(agent_id=agent.id)
        if current_profile is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Agent '{agent.slug}' is not configured for export yet.",
            )
        return self._ensure_runtime_supported_for_version(
            agent=agent,
            version=current_profile,
            runtime_target=runtime_target,
        )

    def _ensure_runtime_supported_for_version(
        self,
        *,
        agent,
        version: AgentVersion,
        runtime_target: str,
    ) -> AgentVersion:
        """Validate runtime support for the stored export profile."""
        export_targets = version.export_targets or []
        if export_targets and runtime_target not in export_targets:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Agent '{agent.slug}' does not support runtime '{runtime_target}'.",
            )

        compatibility = version.compatibility_matrix
        if isinstance(compatibility, dict) and runtime_target in compatibility:
            value = compatibility[runtime_target]
            if isinstance(value, bool) and not value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Agent '{agent.slug}' is incompatible with '{runtime_target}'.",
                )
            if isinstance(value, str) and value.lower() in {"false", "no", "none", "unsupported"}:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Agent '{agent.slug}' is incompatible with '{runtime_target}'.",
                )
            if isinstance(value, dict) and value.get("supported") is False:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Agent '{agent.slug}' is incompatible with '{runtime_target}'.",
                )
        return version

    def _build_codex_profile(
        self,
        *,
        agent,
        manifest: dict[str, Any],
        fallback_description: str,
        fallback_instructions: str,
        codex_options: CodexExportOptions | None = None,
    ) -> dict[str, str | None]:
        """Build normalized Codex role config from agent manifest."""
        codex = manifest.get("codex") if isinstance(manifest.get("codex"), dict) else {}

        model = None
        reasoning_effort = self._normalize_reasoning_effort(
            self._first_non_empty_str(
                codex.get("model_reasoning_effort"),
                manifest.get("model_reasoning_effort"),
                default=self._DEFAULT_REASONING_EFFORT,
            )
        )
        sandbox_mode = self._normalize_sandbox_mode(
            self._first_non_empty_str(
                codex.get("sandbox_mode"),
                manifest.get("sandbox_mode"),
                default=self._DEFAULT_SANDBOX_MODE,
            )
        )
        description = self._first_non_empty_str(
            codex.get("description"),
            manifest.get("description"),
            fallback_description,
            agent.short_description,
            agent.title,
            default="Agent role",
        )
        developer_instructions = self._first_non_empty_str(
            codex.get("developer_instructions"),
            manifest.get("instructions"),
            fallback_instructions,
            default=self._DEFAULT_INSTRUCTIONS,
        )

        if codex_options is not None:
            if codex_options.model:
                model = codex_options.model
            if codex_options.model_reasoning_effort:
                reasoning_effort = codex_options.model_reasoning_effort
            if codex_options.sandbox_mode:
                sandbox_mode = codex_options.sandbox_mode

        return {
            "description": description,
            "model": model,
            "model_reasoning_effort": reasoning_effort,
            "sandbox_mode": sandbox_mode,
            "developer_instructions": developer_instructions,
        }

    def _build_claude_profile(
        self,
        *,
        agent,
        manifest: dict[str, Any],
        fallback_name: str,
        fallback_description: str,
        fallback_prompt: str,
        claude_options: ClaudeExportOptions | None = None,
    ) -> dict[str, str]:
        """Build normalized Claude Code agent profile from agent manifest."""
        claude = manifest.get("claude") if isinstance(manifest.get("claude"), dict) else {}

        name = self._normalize_agent_name(
            self._first_non_empty_str(
                claude.get("name"),
                fallback_name,
                agent.slug,
                default="agent",
            )
        )
        description = self._first_non_empty_str(
            claude.get("description"),
            manifest.get("description"),
            fallback_description,
            agent.short_description,
            agent.title,
            default="Agent role",
        )
        model = self._normalize_claude_model(
            self._first_non_empty_str(
                claude.get("model"),
                default=self._DEFAULT_CLAUDE_MODEL,
            )
        )
        permission_mode = self._normalize_claude_permission_mode(
            self._first_non_empty_str(
                claude.get("permission_mode"),
                claude.get("permissionMode"),
                default=self._DEFAULT_CLAUDE_PERMISSION_MODE,
            )
        )
        prompt = self._first_non_empty_str(
            claude.get("prompt"),
            manifest.get("instructions"),
            fallback_prompt,
            default=self._DEFAULT_INSTRUCTIONS,
        )

        if claude_options is not None:
            if claude_options.model:
                model = claude_options.model
            if claude_options.permission_mode:
                permission_mode = claude_options.permission_mode

        return {
            "name": name,
            "description": description,
            "model": model,
            "permission_mode": permission_mode,
            "prompt": prompt,
        }

    def _build_opencode_profile(
        self,
        *,
        agent,
        manifest: dict[str, Any],
        fallback_description: str,
        fallback_prompt: str,
        opencode_options: OpenCodeExportOptions | None = None,
    ) -> dict[str, str]:
        """Build normalized OpenCode agent profile from agent manifest."""
        opencode = manifest.get("opencode") if isinstance(manifest.get("opencode"), dict) else {}

        description = self._first_non_empty_str(
            opencode.get("description"),
            manifest.get("description"),
            fallback_description,
            agent.short_description,
            agent.title,
            default="Agent role",
        )
        model = self._first_non_empty_str(
            opencode.get("model"),
            default="",
        )
        permission = self._normalize_opencode_permission(
            self._first_non_empty_str(
                opencode.get("permission"),
                default=self._DEFAULT_OPENCODE_PERMISSION,
            )
        )
        prompt = self._first_non_empty_str(
            opencode.get("prompt"),
            manifest.get("instructions"),
            fallback_prompt,
            default=self._DEFAULT_INSTRUCTIONS,
        )

        if opencode_options is not None:
            if opencode_options.model:
                model = opencode_options.model
            if opencode_options.permission:
                permission = opencode_options.permission

        return {
            "description": description,
            "model": model,
            "permission": permission,
            "prompt": prompt,
        }

    @staticmethod
    def _extract_manifest(version: AgentVersion) -> dict[str, Any]:
        """Return manifest payload when present and valid."""
        if isinstance(version.manifest_json, dict):
            return version.manifest_json
        return {}

    @staticmethod
    def _extract_skill_records(manifest: dict[str, Any]) -> list[dict[str, str]]:
        """Return normalized skill attachments from manifest."""
        return normalize_skill_records(manifest.get("skills"), strict=False)

    @staticmethod
    def _extract_markdown_file_records(manifest: dict[str, Any]) -> list[dict[str, str]]:
        """Return normalized markdown file attachments from manifest."""
        return normalize_markdown_file_records(manifest.get("markdown_files"), strict=False)

    @staticmethod
    def _should_archive_agent_payload(payload: dict[str, Any]) -> bool:
        """Return true when single-agent export must become a zip bundle."""
        return bool(payload.get("skills") or payload.get("markdown_files"))

    def _build_agent_bundle_files(
        self,
        *,
        payload: dict[str, Any],
        runtime_target: str,
    ) -> dict[str, str]:
        """Build single-agent zip bundle files for a runtime export."""
        files: dict[str, str] = {}
        slug = str(payload["slug"])

        if runtime_target == RuntimeTarget.CODEX.value:
            files[f"{slug}.toml"] = render_codex_agent_toml(payload["codex"])
        elif runtime_target == RuntimeTarget.CLAUDE_CODE.value:
            files[f"{slug}.md"] = render_claude_agent_markdown(payload["claude"])
        else:
            files[f"{slug}.md"] = render_opencode_agent_markdown(payload["opencode"])

        self._append_agent_asset_files(
            files=files,
            agent_slug=slug,
            runtime_target=runtime_target,
            markdown_files=payload.get("markdown_files") or [],
            skills=payload.get("skills") or [],
            namespaced=False,
        )
        return files

    def _append_team_asset_files(
        self,
        *,
        files: dict[str, str],
        team_items: list[dict[str, Any]],
        runtime_target: str,
    ) -> None:
        """Add markdown and skill attachments for each team item into zip files."""
        for item in team_items:
            self._append_agent_asset_files(
                files=files,
                agent_slug=str(item["agent_slug"]),
                runtime_target=runtime_target,
                markdown_files=item.get("markdown_files") or [],
                skills=item.get("skills") or [],
                namespaced=True,
            )

    def _append_agent_asset_files(
        self,
        *,
        files: dict[str, str],
        agent_slug: str,
        runtime_target: str,
        markdown_files: list[dict[str, str]],
        skills: list[dict[str, str]],
        namespaced: bool,
    ) -> None:
        """Append agent markdown and skill files into export bundle mapping."""
        for markdown_file in markdown_files:
            path = str(markdown_file["path"])
            bundle_path = (
                f"agents/{agent_slug}/{path}"
                if namespaced
                else path
            )
            files[bundle_path] = str(markdown_file["content"]).strip() + "\n"

        for skill in skills:
            skill_slug = str(skill["slug"])
            if runtime_target == RuntimeTarget.CODEX.value:
                if namespaced:
                    skill_path = f".codex/skills/{agent_slug}-{skill_slug}/SKILL.md"
                else:
                    skill_path = f".codex/skills/{skill_slug}/SKILL.md"
            else:
                if namespaced:
                    skill_path = f"skills/{agent_slug}/{skill_slug}/SKILL.md"
                else:
                    skill_path = f"skills/{skill_slug}/SKILL.md"
            content = str(skill["content"]).strip()
            if runtime_target == RuntimeTarget.CODEX.value:
                files[skill_path] = self._render_codex_skill_markdown(
                    slug=skill_slug,
                    description=skill.get("description"),
                    content=content,
                )
            else:
                files[skill_path] = content + "\n"

    @staticmethod
    def _render_codex_skill_markdown(
        *,
        slug: str,
        description: Any,
        content: str,
    ) -> str:
        """Wrap exported Codex skills in YAML frontmatter when the source lacks it."""
        normalized = content.lstrip()
        if normalized.startswith("---\n") or normalized.startswith("---\r\n"):
            return content.rstrip() + "\n"

        description_text = str(description).strip() if isinstance(description, str) else ""
        if not description_text:
            description_text = f"Skill '{slug}' exported from Team Agent Platform."

        lines = [
            "---",
            f"name: {json.dumps(slug, ensure_ascii=False)}",
            f"description: {json.dumps(description_text, ensure_ascii=False)}",
            "---",
            "",
            content,
        ]
        return "\n".join(lines).rstrip() + "\n"

    @staticmethod
    def _as_str_list(value: Any) -> list[str]:
        """Normalize arbitrary value into list[str]."""
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if isinstance(item, (str, int, float)) and str(item)]

    @classmethod
    def _normalize_reasoning_effort(cls, value: str) -> str:
        """Map unsupported values to safe default."""
        normalized = value.strip().lower()
        if normalized not in {"low", "medium", "high"}:
            return cls._DEFAULT_REASONING_EFFORT
        return normalized

    @classmethod
    def _normalize_sandbox_mode(cls, value: str) -> str:
        """Map unsupported values to safe default."""
        normalized = value.strip().lower()
        if normalized not in {"read-only", "workspace-write", "danger-full-access"}:
            return cls._DEFAULT_SANDBOX_MODE
        return normalized

    @classmethod
    def _normalize_claude_model(cls, value: str) -> str:
        """Map unsupported Claude model aliases to safe default."""
        normalized = value.strip()
        if normalized not in {"sonnet", "opus", "haiku", "inherit"}:
            return cls._DEFAULT_CLAUDE_MODEL
        return normalized

    @classmethod
    def _normalize_claude_permission_mode(cls, value: str) -> str:
        """Map unsupported Claude permission modes to safe default."""
        normalized = value.strip()
        if normalized not in {
            "default",
            "acceptEdits",
            "dontAsk",
            "bypassPermissions",
            "plan",
        }:
            return cls._DEFAULT_CLAUDE_PERMISSION_MODE
        return normalized

    @classmethod
    def _normalize_opencode_permission(cls, value: str) -> str:
        """Map unsupported OpenCode permission modes to safe default."""
        normalized = value.strip().lower()
        if normalized not in {"allow", "ask", "deny"}:
            return cls._DEFAULT_OPENCODE_PERMISSION
        return normalized

    @staticmethod
    def _normalize_agent_name(value: str) -> str:
        """Normalize runtime agent names to lowercase hyphenated form."""
        normalized = "".join(
            char.lower() if char.isalnum() else "-"
            for char in value.strip()
        ).strip("-")
        while "--" in normalized:
            normalized = normalized.replace("--", "-")
        return normalized or "agent"

    @staticmethod
    def _first_non_empty_str(*values: Any, default: str) -> str:
        """Return first non-empty string value or default."""
        for value in values:
            if not isinstance(value, str):
                continue
            normalized = value.strip()
            if normalized:
                return normalized
        return default

    @staticmethod
    def _build_result_url(
        *,
        entity_type: str,
        slug: str,
        runtime_target: str,
        codex_options: CodexExportOptions | None = None,
        claude_options: ClaudeExportOptions | None = None,
        opencode_options: OpenCodeExportOptions | None = None,
        bundle_assets: bool = False,
    ) -> str:
        """Build deterministic artifact URL placeholder for MVP exports."""
        if runtime_target == RuntimeTarget.CODEX.value:
            query_params = codex_options.to_query_params() if codex_options else {}
        elif runtime_target == RuntimeTarget.CLAUDE_CODE.value:
            query_params = claude_options.to_query_params() if claude_options else {}
        else:
            query_params = opencode_options.to_query_params() if opencode_options else {}
        query = f"?{urlencode(query_params)}" if query_params else ""
        if entity_type == ExportEntityType.AGENT.value:
            if bundle_assets and runtime_target == RuntimeTarget.CODEX.value:
                return f"/downloads/agent/{slug}/codex.zip{query}"
            if bundle_assets and runtime_target == RuntimeTarget.CLAUDE_CODE.value:
                return f"/downloads/agent/{slug}/claude_code.zip{query}"
            if bundle_assets and runtime_target == RuntimeTarget.OPENCODE.value:
                return f"/downloads/agent/{slug}/opencode.zip{query}"
            if runtime_target == RuntimeTarget.CODEX.value:
                return f"/downloads/agent/{slug}/codex.toml{query}"
            if runtime_target == RuntimeTarget.CLAUDE_CODE.value:
                return f"/downloads/agent/{slug}/claude_code.md{query}"
            return f"/downloads/agent/{slug}/opencode.md{query}"
        if runtime_target == RuntimeTarget.CODEX.value:
            return f"/downloads/team/{slug}/codex.zip{query}"
        if runtime_target == RuntimeTarget.CLAUDE_CODE.value:
            return f"/downloads/team/{slug}/claude_code.zip{query}"
        return f"/downloads/team/{slug}/opencode.zip{query}"

    @staticmethod
    def _ensure_supported_runtime(runtime_target: str) -> None:
        """Restrict current MVP export implementation to supported runtimes."""
        if runtime_target not in {
            RuntimeTarget.CODEX.value,
            RuntimeTarget.CLAUDE_CODE.value,
            RuntimeTarget.OPENCODE.value,
        }:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Only 'codex', 'claude_code', and 'opencode' runtime exports "
                    "are supported in current MVP."
                ),
            )
