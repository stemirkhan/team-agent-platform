"""Codex PTY session endpoints backed by host subprocesses."""

from fastapi import APIRouter, HTTPException, Path, Query, status

from host_executor_app.schemas.codex import (
    CodexSessionEventsResponse,
    CodexSessionRead,
    CodexSessionStart,
)
from host_executor_app.services.codex_session_service import (
    CodexSessionService,
    CodexSessionServiceError,
)

router = APIRouter(prefix="/codex/sessions", tags=["codex"])
codex_session_service = CodexSessionService()


@router.post("/start", response_model=CodexSessionRead, status_code=status.HTTP_201_CREATED)
def start_codex_session(payload: CodexSessionStart) -> CodexSessionRead:
    """Start one Codex session for a prepared workspace."""
    try:
        return codex_session_service.start_session(payload)
    except CodexSessionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/{run_id}", response_model=CodexSessionRead)
def get_codex_session(run_id: str = Path(min_length=1)) -> CodexSessionRead:
    """Return one Codex session by run id."""
    try:
        return codex_session_service.get_session(run_id)
    except CodexSessionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/{run_id}/events", response_model=CodexSessionEventsResponse)
def get_codex_session_events(
    run_id: str = Path(min_length=1),
    offset: int = Query(default=0, ge=0),
) -> CodexSessionEventsResponse:
    """Return incremental terminal output for one Codex session."""
    try:
        return codex_session_service.get_events(run_id, offset)
    except CodexSessionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{run_id}/cancel", response_model=CodexSessionRead)
def cancel_codex_session(run_id: str = Path(min_length=1)) -> CodexSessionRead:
    """Cancel one running Codex session."""
    try:
        return codex_session_service.cancel_session(run_id)
    except CodexSessionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{run_id}/resume", response_model=CodexSessionRead)
def resume_codex_session(run_id: str = Path(min_length=1)) -> CodexSessionRead:
    """Resume one interrupted Codex session."""
    try:
        return codex_session_service.resume_session(run_id)
    except CodexSessionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
