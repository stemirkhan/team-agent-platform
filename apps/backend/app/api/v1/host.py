"""Host diagnostics endpoints for local execution prerequisites."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_operator_user
from app.core.config import get_settings
from app.models.export_job import RuntimeTarget
from app.schemas.host import HostDiagnosticsResponse, HostExecutionReadinessResponse
from app.services.host_execution_service import (
    HostExecutionReadinessService,
    HostExecutionReadinessServiceError,
)

router = APIRouter(
    prefix="/host",
    tags=["host"],
    dependencies=[Depends(get_current_operator_user)],
)
readiness_service = HostExecutionReadinessService(get_settings())


@router.get("/diagnostics", response_model=HostDiagnosticsResponse)
def get_host_diagnostics() -> HostDiagnosticsResponse:
    """Return a live diagnostics snapshot from the host executor bridge."""
    try:
        return readiness_service.get_host_diagnostics()
    except HostExecutionReadinessServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.detail,
        ) from exc


@router.post("/diagnostics/refresh", response_model=HostDiagnosticsResponse)
def refresh_host_diagnostics() -> HostDiagnosticsResponse:
    """Return a fresh host-executor diagnostics snapshot."""
    try:
        return readiness_service.get_host_diagnostics(force_refresh=True)
    except HostExecutionReadinessServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.detail,
        ) from exc


@router.get("/readiness", response_model=HostExecutionReadinessResponse)
def get_host_readiness(
    runtime_target: RuntimeTarget | None = Query(default=None),
) -> HostExecutionReadinessResponse:
    """Return host-executor readiness."""
    return readiness_service.build_readiness(
        runtime_target=runtime_target.value if runtime_target is not None else None
    )


@router.post("/readiness/refresh", response_model=HostExecutionReadinessResponse)
def refresh_host_readiness(
    runtime_target: RuntimeTarget | None = Query(default=None),
) -> HostExecutionReadinessResponse:
    """Return a fresh host-executor readiness snapshot."""
    return readiness_service.build_readiness(
        runtime_target=runtime_target.value if runtime_target is not None else None,
        force_refresh=True,
    )
