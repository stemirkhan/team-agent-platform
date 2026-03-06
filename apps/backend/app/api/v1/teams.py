"""Team catalog and team builder endpoints for MVP."""

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user, get_team_service
from app.models.team import TeamStatus
from app.models.user import User
from app.schemas.team import TeamCreate, TeamDetailsRead, TeamItemCreate, TeamListResponse, TeamRead
from app.services.team_service import TeamService

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=TeamListResponse)
def list_teams(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: TeamStatus | None = Query(default=TeamStatus.PUBLISHED, alias="status"),
    search: str | None = Query(default=None, max_length=255, alias="q"),
    service: TeamService = Depends(get_team_service),
) -> TeamListResponse:
    """Return teams list with optional filters."""
    return service.list_teams(
        limit=limit,
        offset=offset,
        status_filter=status_filter,
        search=search,
    )


@router.post("", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def create_team(
    payload: TeamCreate,
    user: User = Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
) -> TeamRead:
    """Create a new team."""
    return service.create_team(payload, user)


@router.get("/{slug}", response_model=TeamDetailsRead)
def get_team(slug: str, service: TeamService = Depends(get_team_service)) -> TeamDetailsRead:
    """Return team details by slug."""
    return service.get_team(slug)


@router.post("/{slug}/items", response_model=TeamDetailsRead)
def add_team_item(
    slug: str,
    payload: TeamItemCreate,
    user: User = Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
) -> TeamDetailsRead:
    """Add an agent item to the team."""
    return service.add_item(slug, payload, user)


@router.post("/{slug}/publish", response_model=TeamRead)
def publish_team(
    slug: str,
    user: User = Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
) -> TeamRead:
    """Transition team to published state."""
    return service.publish_team(slug, user)
