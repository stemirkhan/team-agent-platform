"""Business logic for team catalog and team builder operations."""

from uuid import UUID

from fastapi import HTTPException, status

from app.models.agent import AgentStatus
from app.models.team import TeamItem, TeamStatus
from app.models.user import User
from app.repositories.agent import AgentRepository
from app.repositories.agent_version import AgentVersionRepository
from app.repositories.team import TeamRepository
from app.schemas.team import (
    TeamCreate,
    TeamDetailsRead,
    TeamItemCreate,
    TeamItemUpdate,
    TeamListResponse,
    TeamRead,
    TeamUpdate,
)


class TeamService:
    """Use-case orchestration for teams."""

    def __init__(
        self,
        team_repository: TeamRepository,
        agent_repository: AgentRepository,
        agent_version_repository: AgentVersionRepository,
    ) -> None:
        self.team_repository = team_repository
        self.agent_repository = agent_repository
        self.agent_version_repository = agent_version_repository

    def create_team(self, payload: TeamCreate, current_user: User):
        """Create a team if slug is unique."""
        existing = self.team_repository.get_by_slug(payload.slug)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Team with the provided slug already exists.",
            )
        return self.team_repository.create(
            payload,
            author_id=current_user.id,
            author_name=current_user.display_name,
        )

    def list_teams(
        self,
        *,
        limit: int,
        offset: int,
        status_filter: TeamStatus | None,
        search: str | None,
    ) -> TeamListResponse:
        """Return paginated team list."""
        status_value = status_filter.value if status_filter else None
        items, total = self.team_repository.list_teams(
            limit=limit,
            offset=offset,
            status=status_value,
            search=search,
        )
        return TeamListResponse(items=items, total=total, limit=limit, offset=offset)

    def list_my_teams(
        self,
        *,
        current_user: User,
        limit: int,
        offset: int,
        status_filter: TeamStatus | None,
    ) -> TeamListResponse:
        """Return paginated list of teams owned by current user."""
        status_value = status_filter.value if status_filter else None
        items, total = self.team_repository.list_by_author(
            author_id=current_user.id,
            limit=limit,
            offset=offset,
            status=status_value,
        )
        return TeamListResponse(items=items, total=total, limit=limit, offset=offset)

    def get_team(self, slug: str) -> TeamDetailsRead:
        """Return team details with item list."""
        team = self._get_team_entity(slug)
        items = self.team_repository.list_items(team.id)
        payload = TeamRead.model_validate(team).model_dump()
        return TeamDetailsRead(**payload, items=items)

    def update_team(self, slug: str, payload: TeamUpdate, current_user: User) -> TeamDetailsRead:
        """Update mutable team fields with a published-team startup prompt exception."""
        team = self._get_team_entity(slug)
        self._ensure_owner(team.author_id, current_user.id)
        if team.status == TeamStatus.DRAFT.value:
            pass
        elif team.status == TeamStatus.PUBLISHED.value:
            mutable_fields = payload.model_fields_set
            if mutable_fields and not mutable_fields.issubset({"startup_prompt"}):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Published teams only allow startup_prompt updates.",
                )
        else:
            self._ensure_draft(team.status)
        self.team_repository.update(team, payload)
        return self.get_team(slug)

    def add_item(self, slug: str, payload: TeamItemCreate, current_user: User) -> TeamDetailsRead:
        """Add a published agent into a draft team."""
        team = self._get_team_entity(slug)
        self._ensure_owner(team.author_id, current_user.id)
        self._ensure_draft(team.status)
        self._ensure_unique_role_name(team.id, payload.role_name)

        agent_version = self._get_current_agent_version(payload.agent_slug)
        insert_index = self._normalize_insert_index(
            requested_index=payload.order_index,
            team_id=team.id,
        )

        created_item = self.team_repository.create_item(
            team=team,
            agent_version=agent_version,
            payload=payload,
            order_index=insert_index,
        )
        self._reorder_after_add(team_id=team.id, item_id=created_item.id, insert_index=insert_index)
        return self.get_team(slug)

    def update_item(
        self,
        slug: str,
        item_id: UUID,
        payload: TeamItemUpdate,
        current_user: User,
    ) -> TeamDetailsRead:
        """Update mutable fields of one draft team item."""
        team = self._get_team_entity(slug)
        self._ensure_owner(team.author_id, current_user.id)
        self._ensure_draft(team.status)

        item = self.team_repository.get_item_by_id(team_id=team.id, item_id=item_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team item not found.",
            )

        items = self.team_repository.list_item_entities(team.id)
        current_index = next(
            (index for index, existing in enumerate(items) if existing.id == item.id),
            None,
        )
        if current_index is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team item not found.",
            )

        if payload.role_name is not None:
            self._ensure_unique_role_name(team.id, payload.role_name, exclude_item_id=item.id)
            item.role_name = payload.role_name
        if payload.is_required is not None:
            item.is_required = payload.is_required
        if "config_json" in payload.model_fields_set:
            item.config_json = payload.config_json
        if payload.agent_slug is not None:
            agent_version = self._get_current_agent_version(payload.agent_slug)
            item.agent_version_id = agent_version.id

        desired_index = self._clamp_index(
            requested_index=payload.order_index,
            length=max(len(items) - 1, 0),
            fallback=current_index,
        )
        reordered_items = [existing for existing in items if existing.id != item.id]
        reordered_items.insert(desired_index, item)
        self._persist_item_order(reordered_items)
        return self.get_team(slug)

    def delete_item(self, slug: str, item_id: UUID, current_user: User) -> TeamDetailsRead:
        """Delete one team item from a draft team."""
        team = self._get_team_entity(slug)
        self._ensure_owner(team.author_id, current_user.id)
        self._ensure_draft(team.status)

        item = self.team_repository.get_item_by_id(team_id=team.id, item_id=item_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team item not found.",
            )

        self.team_repository.delete_item(item)
        self._persist_item_order(self.team_repository.list_item_entities(team.id))
        return self.get_team(slug)

    def publish_team(self, slug: str, current_user: User):
        """Move team to published state."""
        team = self._get_team_entity(slug)
        self._ensure_owner(team.author_id, current_user.id)
        self._ensure_draft(team.status)
        self._validate_team_for_publish(team.id)
        return self.team_repository.update_status(team, TeamStatus.PUBLISHED.value)

    def _get_team_entity(self, slug: str):
        """Load team by slug or raise 404."""
        entity = self.team_repository.get_by_slug(slug)
        if entity is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found.")
        return entity

    def _get_current_agent_version(self, agent_slug: str):
        """Return current internal profile row for a published agent."""
        agent = self.agent_repository.get_by_slug(agent_slug)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found.",
            )
        if agent.status != AgentStatus.PUBLISHED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only published agents can be added to a team.",
            )
        agent_version = self.agent_version_repository.get_latest_for_agent(agent_id=agent.id)
        if agent_version is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Agent '{agent.slug}' is not configured for team usage yet.",
            )
        return agent_version

    def _validate_team_for_publish(self, team_id: UUID) -> None:
        """Validate draft team before publication."""
        items = self.team_repository.list_item_entities(team_id)
        if not items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot publish empty team.",
            )

        seen_roles: set[str] = set()
        reordered = sorted(items, key=lambda item: (item.order_index, str(item.id)))

        for expected_index, item in enumerate(reordered):
            normalized_role = item.role_name.strip().lower()
            if not normalized_role:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Each team item must have a role name.",
                )
            if normalized_role in seen_roles:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Team role names must be unique.",
                )
            seen_roles.add(normalized_role)
            agent_version = self.agent_version_repository.get_by_id(
                version_id=item.agent_version_id
            )
            if agent_version is None or agent_version.agent is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Each team item must reference a configured published agent.",
                )
            if agent_version.agent.status != AgentStatus.PUBLISHED.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Each team item must reference a configured published agent.",
                )
            item.order_index = expected_index

        self.team_repository.save_items(reordered)

    def _ensure_unique_role_name(
        self,
        team_id: UUID,
        role_name: str,
        exclude_item_id: UUID | None = None,
    ) -> None:
        """Reject duplicate role names in one team."""
        normalized_role = role_name.strip().lower()
        if not normalized_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role name cannot be empty.",
            )

        items = self.team_repository.list_item_entities(team_id)
        for item in items:
            if exclude_item_id is not None and item.id == exclude_item_id:
                continue
            if item.role_name.strip().lower() == normalized_role:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Team role names must be unique.",
                )

    def _normalize_insert_index(self, *, requested_index: int | None, team_id: UUID) -> int:
        """Return safe insertion index inside current team bounds."""
        items = self.team_repository.list_item_entities(team_id)
        return self._clamp_index(
            requested_index=requested_index,
            length=len(items),
            fallback=len(items),
        )

    @classmethod
    def _clamp_index(cls, *, requested_index: int | None, length: int, fallback: int) -> int:
        """Clamp requested order index to a valid insertion point."""
        if requested_index is None:
            return fallback
        if requested_index < 0:
            return 0
        if requested_index > length:
            return length
        return requested_index

    def _reorder_after_add(self, *, team_id: UUID, item_id: UUID, insert_index: int) -> None:
        """Rebuild sequential order after adding a new team item."""
        items = self.team_repository.list_item_entities(team_id)
        target = next((item for item in items if item.id == item_id), None)
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team item not found.",
            )

        remaining = [item for item in items if item.id != item_id]
        remaining.insert(insert_index, target)
        self._persist_item_order(remaining)

    def _persist_item_order(self, items: list[TeamItem]) -> None:
        """Write sequential order indexes for the provided item sequence."""
        for index, item in enumerate(items):
            item.order_index = index
        self.team_repository.save_items(items)

    @staticmethod
    def _ensure_owner(author_id: UUID | None, actor_user_id: UUID) -> None:
        """Ensure mutating action is made by the resource owner."""
        if author_id != actor_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the author can modify this team.",
            )

    @staticmethod
    def _ensure_draft(status_value: str) -> None:
        """Allow structural edits only for draft teams."""
        if status_value != TeamStatus.DRAFT.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only draft teams can be modified.",
            )
