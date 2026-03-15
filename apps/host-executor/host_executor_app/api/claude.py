"""Claude Code session endpoints backed by host subprocesses."""

from fastapi import APIRouter, HTTPException, Path, Query, status

from host_executor_app.schemas.claude import (
    ClaudeSessionEventsResponse,
    ClaudeSessionRead,
    ClaudeSessionStart,
)
from host_executor_app.services.claude_session_service import (
    ClaudeSessionService,
    ClaudeSessionServiceError,
)

router = APIRouter(prefix="/claude/sessions", tags=["claude"])
claude_session_service = ClaudeSessionService()


@router.post("/start", response_model=ClaudeSessionRead, status_code=status.HTTP_201_CREATED)
def start_claude_session(payload: ClaudeSessionStart) -> ClaudeSessionRead:
    """Start one Claude session for a prepared workspace."""
    try:
        return claude_session_service.start_session(payload)
    except ClaudeSessionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/{run_id}", response_model=ClaudeSessionRead)
def get_claude_session(run_id: str = Path(min_length=1)) -> ClaudeSessionRead:
    """Return one Claude session by run id."""
    try:
        return claude_session_service.get_session(run_id)
    except ClaudeSessionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/{run_id}/events", response_model=ClaudeSessionEventsResponse)
def get_claude_session_events(
    run_id: str = Path(min_length=1),
    offset: int = Query(default=0, ge=0),
) -> ClaudeSessionEventsResponse:
    """Return incremental terminal output for one Claude session."""
    try:
        return claude_session_service.get_events(run_id, offset)
    except ClaudeSessionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{run_id}/cancel", response_model=ClaudeSessionRead)
def cancel_claude_session(run_id: str = Path(min_length=1)) -> ClaudeSessionRead:
    """Cancel one running Claude session."""
    try:
        return claude_session_service.cancel_session(run_id)
    except ClaudeSessionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{run_id}/resume", response_model=ClaudeSessionRead)
def resume_claude_session(run_id: str = Path(min_length=1)) -> ClaudeSessionRead:
    """Resume one interrupted Claude session."""
    try:
        return claude_session_service.resume_session(run_id)
    except ClaudeSessionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
