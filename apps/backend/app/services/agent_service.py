"""Business logic for agent lifecycle and catalog queries."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.models.agent import AgentStatus
from app.models.user import User
from app.repositories.agent import AgentRepository
from app.repositories.agent_version import AgentVersionRepository
from app.schemas.agent import AgentCreate, AgentListResponse, AgentRead, AgentUpdate
from app.utils.agent_assets import (
    merge_manifest_assets,
    normalize_markdown_file_records,
    normalize_skill_records,
)


class AgentService:
    """Use-case orchestration for published agents."""

    def __init__(
        self,
        repository: AgentRepository,
        agent_version_repository: AgentVersionRepository,
    ) -> None:
        self.repository = repository
        self.agent_version_repository = agent_version_repository

    def create_agent(self, payload: AgentCreate, current_user: User):
        """Create an agent if slug is unique."""
        existing = self.repository.get_by_slug(payload.slug)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Agent with the provided slug already exists.",
            )
        return self.repository.create(
            payload,
            author_id=current_user.id,
            author_name=current_user.display_name,
        )

    def list_agents(
        self,
        *,
        limit: int,
        offset: int,
        status_filter: AgentStatus | None,
        category: str | None,
        search: str | None,
    ) -> AgentListResponse:
        """Return paginated list of agents."""
        status_value = status_filter.value if status_filter else None
        items, total = self.repository.list(
            limit=limit,
            offset=offset,
            status=status_value,
            category=category,
            search=search,
        )
        return AgentListResponse(items=items, total=total, limit=limit, offset=offset)

    def get_agent(self, slug: str):
        """Return an agent or raise 404."""
        entity = self.repository.get_by_slug(slug)
        if entity is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
        return AgentRead.model_validate(entity)

    def get_draft_agent(self, slug: str, current_user: User):
        """Return the pending draft revision for a published agent."""
        entity = self._get_agent_entity(slug)
        self._ensure_owner(entity.author_id, current_user.id)
        self._ensure_published(entity.status)
        self._ensure_draft_revision_exists(entity)
        return self._serialize_draft_agent(entity)

    def create_draft_revision(self, slug: str, current_user: User):
        """Create a draft revision from the current published agent snapshot."""
        entity = self._get_agent_entity(slug)
        self._ensure_owner(entity.author_id, current_user.id)
        self._ensure_published(entity.status)
        self._ensure_current_profile(entity)

        if entity.has_draft_revision:
            return self._serialize_draft_agent(entity)

        self.repository.update(
            entity,
            fields={
                "draft_title": entity.title,
                "draft_short_description": entity.short_description,
                "draft_full_description": entity.full_description,
                "draft_category": entity.category,
                "draft_updated_at": datetime.now(UTC),
            },
        )
        self.agent_version_repository.create_draft_profile_from_current(agent=entity)
        return self.get_draft_agent(slug, current_user)

    def update_agent(self, slug: str, payload: AgentUpdate, current_user: User):
        """Update mutable agent fields and current export profile."""
        entity = self._get_agent_entity(slug)
        self._ensure_owner(entity.author_id, current_user.id)
        self._ensure_draft(entity.status)

        direct_fields = payload.model_dump(
            exclude_unset=True,
            exclude={
                "manifest_json",
                "source_archive_url",
                "compatibility_matrix",
                "export_targets",
                "install_instructions",
                "skills",
                "markdown_files",
            },
        )
        if direct_fields:
            self.repository.update(entity, fields=direct_fields)

        if self._has_profile_updates(payload):
            try:
                manifest = self._build_manifest(
                    manifest_json=payload.manifest_json,
                    skills=payload.skills,
                    markdown_files=payload.markdown_files,
                    current_manifest=entity.manifest_json,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(exc),
                ) from exc
            self.agent_version_repository.upsert_current_profile(
                agent=entity,
                manifest_json=manifest,
                source_archive_url=payload.source_archive_url
                if "source_archive_url" in payload.model_fields_set
                else entity.source_archive_url,
                compatibility_matrix=payload.compatibility_matrix
                if "compatibility_matrix" in payload.model_fields_set
                else entity.compatibility_matrix,
                export_targets=payload.export_targets
                if "export_targets" in payload.model_fields_set
                else entity.export_targets,
                install_instructions=payload.install_instructions
                if "install_instructions" in payload.model_fields_set
                else entity.install_instructions,
            )

        return self.get_agent(slug)

    def update_draft_agent(self, slug: str, payload: AgentUpdate, current_user: User):
        """Update the pending draft revision for one published agent."""
        entity = self._get_agent_entity(slug)
        self._ensure_owner(entity.author_id, current_user.id)
        self._ensure_published(entity.status)
        self._ensure_draft_revision_exists(entity)

        direct_fields = payload.model_dump(
            exclude_unset=True,
            exclude={
                "manifest_json",
                "source_archive_url",
                "compatibility_matrix",
                "export_targets",
                "install_instructions",
                "skills",
                "markdown_files",
            },
        )
        if direct_fields:
            mapped_fields = {f"draft_{key}": value for key, value in direct_fields.items()}
            mapped_fields["draft_updated_at"] = datetime.now(UTC)
            self.repository.update(entity, fields=mapped_fields)

        if self._has_profile_updates(payload):
            draft_profile = self.agent_version_repository.get_by_version(
                agent_id=entity.id,
                version="draft",
            )
            current_manifest = draft_profile.manifest_json if draft_profile else None
            try:
                manifest = self._build_manifest(
                    manifest_json=payload.manifest_json,
                    skills=payload.skills,
                    markdown_files=payload.markdown_files,
                    current_manifest=current_manifest,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(exc),
                ) from exc
            self.agent_version_repository.upsert_draft_profile(
                agent=entity,
                manifest_json=manifest,
                source_archive_url=payload.source_archive_url
                if "source_archive_url" in payload.model_fields_set
                else draft_profile.source_archive_url
                if draft_profile
                else entity.source_archive_url,
                compatibility_matrix=payload.compatibility_matrix
                if "compatibility_matrix" in payload.model_fields_set
                else draft_profile.compatibility_matrix
                if draft_profile
                else entity.compatibility_matrix,
                export_targets=payload.export_targets
                if "export_targets" in payload.model_fields_set
                else draft_profile.export_targets
                if draft_profile
                else entity.export_targets,
                install_instructions=payload.install_instructions
                if "install_instructions" in payload.model_fields_set
                else draft_profile.install_instructions
                if draft_profile
                else entity.install_instructions,
            )

        return self.get_draft_agent(slug, current_user)

    def publish_agent(self, slug: str, current_user: User):
        """Move agent to published status."""
        entity = self._get_agent_entity(slug)
        self._ensure_owner(entity.author_id, current_user.id)
        self._ensure_current_profile(entity)
        updated = self.repository.update_status(entity, AgentStatus.PUBLISHED.value)
        return AgentRead.model_validate(updated)

    def publish_draft_revision(self, slug: str, current_user: User):
        """Promote a pending draft revision into the live published agent."""
        entity = self._get_agent_entity(slug)
        self._ensure_owner(entity.author_id, current_user.id)
        self._ensure_published(entity.status)
        self._ensure_draft_revision_exists(entity)

        self.repository.update(
            entity,
            fields={
                "title": entity.draft_title or entity.title,
                "short_description": entity.draft_short_description or entity.short_description,
                "full_description": entity.draft_full_description,
                "category": entity.draft_category,
                "draft_title": None,
                "draft_short_description": None,
                "draft_full_description": None,
                "draft_category": None,
                "draft_updated_at": None,
            },
        )
        self.agent_version_repository.promote_draft_profile(agent=entity)
        return self.get_agent(slug)

    def _get_agent_entity(self, slug: str):
        """Return ORM entity or raise 404."""
        entity = self.repository.get_by_slug(slug)
        if entity is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
        return entity

    def _ensure_current_profile(self, agent) -> None:
        """Ensure published/exportable agent has a hidden current profile row."""
        if agent.current_version is not None:
            return

        manifest = {
            "description": agent.full_description or agent.short_description,
            "instructions": agent.full_description or agent.short_description,
            "codex": {
                "description": agent.short_description,
                "developer_instructions": agent.full_description or agent.short_description,
            },
        }
        self.agent_version_repository.upsert_current_profile(
            agent=agent,
            manifest_json=manifest,
            source_archive_url=None,
            compatibility_matrix={"codex": True, "claude_code": True},
            export_targets=["codex", "claude_code"],
            install_instructions=agent.full_description or agent.short_description,
        )

    @staticmethod
    def _has_profile_updates(payload: AgentUpdate) -> bool:
        """Return true when current export profile fields are present."""
        profile_fields = {
            "manifest_json",
            "source_archive_url",
            "compatibility_matrix",
            "export_targets",
            "install_instructions",
            "skills",
            "markdown_files",
        }
        return any(field in payload.model_fields_set for field in profile_fields)

    @staticmethod
    def _build_manifest(
        *,
        manifest_json: dict[str, Any] | None,
        skills,
        markdown_files,
        current_manifest: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Merge current manifest with updated attachments."""
        base_manifest = (
            manifest_json
            if isinstance(manifest_json, dict)
            else current_manifest
            if isinstance(current_manifest, dict)
            else None
        )

        if skills is None:
            skills_source = base_manifest.get("skills") if base_manifest else None
        else:
            skills_source = [item.model_dump(exclude_none=True) for item in skills]

        if markdown_files is None:
            markdown_source = base_manifest.get("markdown_files") if base_manifest else None
        else:
            markdown_source = [item.model_dump() for item in markdown_files]

        normalized_skills = normalize_skill_records(skills_source, strict=True)
        normalized_markdown_files = normalize_markdown_file_records(
            markdown_source,
            strict=True,
        )
        return merge_manifest_assets(
            manifest=base_manifest,
            skills=normalized_skills,
            markdown_files=normalized_markdown_files,
        )

    def _serialize_draft_agent(self, agent) -> AgentRead:
        """Expose one pending draft revision through the regular AgentRead schema."""
        draft_profile = self.agent_version_repository.get_by_version(
            agent_id=agent.id,
            version="draft",
        )
        if draft_profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Draft revision not found.",
            )

        payload = {
            "id": agent.id,
            "slug": agent.slug,
            "title": agent.draft_title or agent.title,
            "short_description": agent.draft_short_description or agent.short_description,
            "full_description": agent.draft_full_description,
            "category": agent.draft_category,
            "author_id": agent.author_id,
            "author_name": agent.author_name,
            "status": AgentStatus.DRAFT,
            "verification_status": agent.verification_status,
            "created_at": agent.created_at,
            "updated_at": agent.draft_updated_at or agent.updated_at,
            "manifest_json": draft_profile.manifest_json,
            "source_archive_url": draft_profile.source_archive_url,
            "compatibility_matrix": draft_profile.compatibility_matrix,
            "export_targets": draft_profile.export_targets,
            "install_instructions": draft_profile.install_instructions,
        }
        return AgentRead.model_validate(payload)

    @staticmethod
    def _ensure_owner(author_id: UUID | None, actor_user_id: UUID) -> None:
        """Ensure mutating action is made by the resource owner."""
        if author_id != actor_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the author can modify this agent.",
            )

    @staticmethod
    def _ensure_draft(status_value: str) -> None:
        """Allow live edits only for draft agents."""
        if status_value != AgentStatus.DRAFT.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Published agents require a draft revision before editing.",
            )

    @staticmethod
    def _ensure_published(status_value: str) -> None:
        """Require a published agent for revision-only operations."""
        if status_value != AgentStatus.PUBLISHED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only published agents support draft revisions.",
            )

    @staticmethod
    def _ensure_draft_revision_exists(agent) -> None:
        """Require an existing draft revision on the published agent."""
        if not agent.has_draft_revision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Draft revision not found.",
            )
