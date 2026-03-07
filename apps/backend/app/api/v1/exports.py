"""Export endpoints for agents and teams."""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user, get_export_service
from app.models.user import User
from app.schemas.export import ExportCreate, ExportRead
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


@router.post("/teams/{slug}", response_model=ExportRead, status_code=status.HTTP_201_CREATED)
def create_team_export(
    slug: str,
    payload: ExportCreate,
    user: User = Depends(get_current_user),
    service: ExportService = Depends(get_export_service),
) -> ExportRead:
    """Create export job for a team."""
    return service.create_team_export(slug=slug, payload=payload, current_user=user)


@router.get("/{export_id}", response_model=ExportRead)
def get_export(
    export_id: UUID,
    user: User = Depends(get_current_user),
    service: ExportService = Depends(get_export_service),
) -> ExportRead:
    """Return export job by id."""
    return service.get_export(export_id=export_id, current_user=user)
