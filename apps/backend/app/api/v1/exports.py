"""Export endpoints for agents and teams."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user, get_export_service
from app.models.user import User
from app.schemas.export import ExportCreate, ExportListResponse, ExportRead
from app.services.export_service import ExportService

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post("/agents/{slug}", response_model=ExportRead, status_code=status.HTTP_201_CREATED)
def create_agent_export(
    slug: str,
    payload: ExportCreate,
    user: User = Depends(get_current_user),
    service: ExportService = Depends(get_export_service),
) -> ExportRead:
    """Create export job for an agent."""
    return service.create_agent_export(slug=slug, payload=payload, current_user=user)


@router.get("/agents/{slug}", response_model=ExportListResponse)
def list_agent_exports(
    slug: str,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    service: ExportService = Depends(get_export_service),
) -> ExportListResponse:
    """Return export jobs for one agent and current user."""
    return service.list_agent_exports(slug=slug, current_user=user, limit=limit, offset=offset)


@router.post("/teams/{slug}", response_model=ExportRead, status_code=status.HTTP_201_CREATED)
def create_team_export(
    slug: str,
    payload: ExportCreate,
    user: User = Depends(get_current_user),
    service: ExportService = Depends(get_export_service),
) -> ExportRead:
    """Create export job for a team."""
    return service.create_team_export(slug=slug, payload=payload, current_user=user)


@router.get("/teams/{slug}", response_model=ExportListResponse)
def list_team_exports(
    slug: str,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    service: ExportService = Depends(get_export_service),
) -> ExportListResponse:
    """Return export jobs for one team and current user."""
    return service.list_team_exports(slug=slug, current_user=user, limit=limit, offset=offset)


@router.get("/{export_id}", response_model=ExportRead)
def get_export(
    export_id: UUID,
    user: User = Depends(get_current_user),
    service: ExportService = Depends(get_export_service),
) -> ExportRead:
    """Return export job by id."""
    return service.get_export(export_id=export_id, current_user=user)
