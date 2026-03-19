"""First-run bootstrap and platform setup flow."""

from fastapi import HTTPException, status

from app.core.config import Settings
from app.core.security import create_access_token, hash_password
from app.models.user import UserRole
from app.repositories.agent import AgentRepository
from app.repositories.agent_version import AgentVersionRepository
from app.repositories.platform_settings import PlatformSettingsRepository
from app.repositories.team import TeamRepository
from app.repositories.user import UserRepository
from app.schemas.agent import AgentCreate, AgentUpdate
from app.schemas.auth import (
    BootstrapSetupRequest,
    BootstrapSetupResponse,
    BootstrapStatusRead,
)
from app.schemas.team import TeamCreate, TeamItemCreate
from app.schemas.user import UserCreateInternal, UserRead
from app.services.agent_service import AgentService
from app.services.starter_catalog import STARTER_AGENTS, STARTER_TEAM, STARTER_TEAM_SLUG
from app.services.team_service import TeamService


class BootstrapService:
    """Setup flow used before the first platform owner exists."""

    def __init__(
        self,
        user_repository: UserRepository,
        platform_settings_repository: PlatformSettingsRepository,
        agent_repository: AgentRepository,
        agent_version_repository: AgentVersionRepository,
        team_repository: TeamRepository,
        settings: Settings,
    ) -> None:
        self.user_repository = user_repository
        self.platform_settings_repository = platform_settings_repository
        self.agent_repository = agent_repository
        self.agent_version_repository = agent_version_repository
        self.team_repository = team_repository
        self.settings = settings

    def get_status(self) -> BootstrapStatusRead:
        """Return whether the platform still requires first-run setup."""
        owner = self.user_repository.get_owner()
        return BootstrapStatusRead(
            setup_required=owner is None,
            allow_open_registration=self.platform_settings_repository.get_effective_allow_open_registration(
                default_value=self.settings.allow_open_registration
            ),
        )

    def bootstrap(self, payload: BootstrapSetupRequest) -> BootstrapSetupResponse:
        """Create the first admin account and optional starter catalog."""
        if self.user_repository.get_owner() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Platform setup is already completed.",
            )

        normalized_email = payload.email.strip().lower()
        if self.user_repository.get_by_email(normalized_email) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists.",
            )

        self.platform_settings_repository.set_allow_open_registration(
            value=payload.allow_open_registration,
            default_value=self.settings.allow_open_registration,
        )

        user = self.user_repository.create(
            UserCreateInternal(
                email=normalized_email,
                password_hash=hash_password(payload.password),
                display_name=payload.display_name.strip(),
                role=UserRole.ADMIN,
            )
        )
        token = create_access_token(user_id=user.id)

        seeded_team_slug = None
        if payload.seed_starter_team:
            self._seed_starter_team_catalog(user)
            seeded_team_slug = STARTER_TEAM_SLUG

        return BootstrapSetupResponse(
            access_token=token,
            user=UserRead.model_validate(user),
            bootstrap_status=self.get_status(),
            seeded_team_slug=seeded_team_slug,
        )

    def _seed_starter_team_catalog(self, current_user) -> None:
        """Create the optional starter agents and the default delivery squad."""
        agent_service = AgentService(
            repository=self.agent_repository,
            agent_version_repository=self.agent_version_repository,
        )
        team_service = TeamService(
            team_repository=self.team_repository,
            agent_repository=self.agent_repository,
            agent_version_repository=self.agent_version_repository,
        )

        for agent_data in STARTER_AGENTS:
            agent_service.create_agent(
                AgentCreate(
                    slug=agent_data["slug"],
                    title=agent_data["title"],
                    short_description=agent_data["short_description"],
                    full_description=agent_data["full_description"],
                    category=agent_data["category"],
                ),
                current_user=current_user,
            )
            agent_service.update_agent(
                agent_data["slug"],
                AgentUpdate(
                    manifest_json=agent_data["manifest_json"],
                    compatibility_matrix=agent_data["compatibility_matrix"],
                    export_targets=agent_data["export_targets"],
                    install_instructions=agent_data["install_instructions"],
                    skills=agent_data["skills"],
                    markdown_files=agent_data["markdown_files"],
                ),
                current_user=current_user,
            )
            agent_service.publish_agent(agent_data["slug"], current_user=current_user)

        team_service.create_team(
            TeamCreate(
                slug=STARTER_TEAM["slug"],
                title=STARTER_TEAM["title"],
                description=STARTER_TEAM["description"],
                startup_prompt=STARTER_TEAM["startup_prompt"],
            ),
            current_user=current_user,
        )
        for item in STARTER_TEAM["items"]:
            team_service.add_item(
                STARTER_TEAM["slug"],
                TeamItemCreate(
                    agent_slug=item["agent_slug"],
                    role_name=item["role_name"],
                    order_index=item["order_index"],
                    is_required=True,
                ),
                current_user=current_user,
            )
        team_service.publish_team(STARTER_TEAM["slug"], current_user=current_user)
