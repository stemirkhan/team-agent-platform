"""Current authenticated user endpoints."""

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_team_service
from app.models.team import TeamStatus
from app.models.user import User
from app.schemas.team import TeamListResponse
from app.schemas.user import UserRead
from app.services.team_service import TeamService

router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserRead)
def get_me(user=Depends(get_current_user)) -> UserRead:
    """Return current authenticated user."""
    return UserRead.model_validate(user)


@router.get("/me/teams", response_model=TeamListResponse)
def get_my_teams(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: TeamStatus | None = Query(default=None, alias="status"),
    user: User = Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
) -> TeamListResponse:
    """Return teams owned by current authenticated user."""
    return service.list_my_teams(
        current_user=user,
        limit=limit,
        offset=offset,
        status_filter=status_filter,
    )
