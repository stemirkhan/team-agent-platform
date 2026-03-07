"""Dependency providers for API routes."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_access_token
from app.repositories.agent import AgentRepository
from app.repositories.agent_version import AgentVersionRepository
from app.repositories.export_job import ExportJobRepository
from app.repositories.review import ReviewRepository
from app.repositories.team import TeamRepository
from app.repositories.user import UserRepository
from app.services.agent_service import AgentService
from app.services.agent_version_service import AgentVersionService
from app.services.auth_service import AuthService
from app.services.export_service import ExportService
from app.services.review_service import ReviewService
from app.services.team_service import TeamService

bearer_scheme = HTTPBearer(auto_error=True)


def get_agent_service(db: Session = Depends(get_db)) -> AgentService:
    """Build AgentService with request-scoped DB session."""
    repository = AgentRepository(db)
    return AgentService(repository)


def get_agent_version_service(db: Session = Depends(get_db)) -> AgentVersionService:
    """Build AgentVersionService with request-scoped DB session."""
    agent_repository = AgentRepository(db)
    agent_version_repository = AgentVersionRepository(db)
    return AgentVersionService(agent_repository, agent_version_repository)


def get_team_service(db: Session = Depends(get_db)) -> TeamService:
    """Build TeamService with request-scoped DB session."""
    team_repository = TeamRepository(db)
    agent_repository = AgentRepository(db)
    return TeamService(team_repository, agent_repository)


def get_export_service(db: Session = Depends(get_db)) -> ExportService:
    """Build ExportService with request-scoped DB session."""
    export_repository = ExportJobRepository(db)
    agent_repository = AgentRepository(db)
    agent_version_repository = AgentVersionRepository(db)
    team_repository = TeamRepository(db)
    return ExportService(
        export_repository,
        agent_repository,
        agent_version_repository,
        team_repository,
    )


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """Build AuthService with request-scoped DB session."""
    user_repository = UserRepository(db)
    return AuthService(user_repository)


def get_review_service(db: Session = Depends(get_db)) -> ReviewService:
    """Build ReviewService with request-scoped DB session."""
    review_repository = ReviewRepository(db)
    agent_repository = AgentRepository(db)
    team_repository = TeamRepository(db)
    return ReviewService(review_repository, agent_repository, team_repository)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Resolve current user from bearer JWT token."""
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
        )
    return auth_service.get_user_by_id(user_id)
