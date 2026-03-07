"""Agent catalog endpoints for MVP."""

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_agent_service,
    get_agent_version_service,
    get_current_user,
    get_review_service,
)
from app.models.agent import AgentStatus
from app.models.user import User
from app.schemas.agent import AgentCreate, AgentListResponse, AgentRead
from app.schemas.agent_version import AgentVersionCreate, AgentVersionListResponse, AgentVersionRead
from app.schemas.review import ReviewCreate, ReviewListResponse, ReviewRead
from app.services.agent_service import AgentService
from app.services.agent_version_service import AgentVersionService
from app.services.review_service import ReviewService

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=AgentListResponse)
def list_agents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: AgentStatus | None = Query(default=AgentStatus.PUBLISHED, alias="status"),
    category: str | None = Query(default=None, max_length=120),
    search: str | None = Query(default=None, max_length=255, alias="q"),
    service: AgentService = Depends(get_agent_service),
) -> AgentListResponse:
    """Return catalog list with optional filters."""
    return service.list_agents(
        limit=limit,
        offset=offset,
        status_filter=status_filter,
        category=category,
        search=search,
    )


@router.post("", response_model=AgentRead, status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: AgentCreate,
    user: User = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
) -> AgentRead:
    """Create a new agent record."""
    return service.create_agent(payload, user)


@router.get("/{slug}", response_model=AgentRead)
def get_agent(slug: str, service: AgentService = Depends(get_agent_service)) -> AgentRead:
    """Return agent details by slug."""
    return service.get_agent(slug)


@router.post("/{slug}/publish", response_model=AgentRead)
def publish_agent(
    slug: str,
    user: User = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
) -> AgentRead:
    """Transition agent to published state."""
    return service.publish_agent(slug, user)


@router.get("/{slug}/versions", response_model=AgentVersionListResponse)
def list_agent_versions(
    slug: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: AgentVersionService = Depends(get_agent_version_service),
) -> AgentVersionListResponse:
    """Return paginated versions for an agent."""
    return service.list_versions(slug=slug, limit=limit, offset=offset)


@router.post(
    "/{slug}/versions",
    response_model=AgentVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_agent_version(
    slug: str,
    payload: AgentVersionCreate,
    user: User = Depends(get_current_user),
    service: AgentVersionService = Depends(get_agent_version_service),
) -> AgentVersionRead:
    """Create new version for an owned agent."""
    return service.create_version(slug=slug, payload=payload, current_user=user)


@router.get("/{slug}/versions/{version}", response_model=AgentVersionRead)
def get_agent_version(
    slug: str,
    version: str,
    service: AgentVersionService = Depends(get_agent_version_service),
) -> AgentVersionRead:
    """Return details of a specific agent version."""
    return service.get_version(slug=slug, version=version)


@router.get("/{slug}/reviews", response_model=ReviewListResponse)
def list_agent_reviews(
    slug: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: ReviewService = Depends(get_review_service),
) -> ReviewListResponse:
    """Return paginated reviews for a published agent."""
    return service.list_agent_reviews(slug=slug, limit=limit, offset=offset)


@router.post("/{slug}/reviews", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
def create_agent_review(
    slug: str,
    payload: ReviewCreate,
    user: User = Depends(get_current_user),
    service: ReviewService = Depends(get_review_service),
) -> ReviewRead:
    """Create review for a published agent."""
    return service.create_agent_review(slug=slug, payload=payload, current_user=user)
