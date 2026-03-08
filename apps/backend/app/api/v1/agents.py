"""Agent catalog endpoints for MVP."""

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_agent_service,
    get_current_user,
)
from app.models.agent import AgentStatus
from app.models.user import User
from app.schemas.agent import AgentCreate, AgentListResponse, AgentRead, AgentUpdate
from app.services.agent_service import AgentService

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


@router.patch("/{slug}", response_model=AgentRead)
def update_agent(
    slug: str,
    payload: AgentUpdate,
    user: User = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
) -> AgentRead:
    """Update agent metadata and current export profile."""
    return service.update_agent(slug, payload, user)


@router.post("/{slug}/publish", response_model=AgentRead)
def publish_agent(
    slug: str,
    user: User = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
) -> AgentRead:
    """Transition agent to published state."""
    return service.publish_agent(slug, user)
