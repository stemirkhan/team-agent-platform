"""Run lifecycle endpoints for local-first Codex execution."""

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status

from app.api.deps import get_auth_service, get_current_user, get_run_service
from app.core.security import decode_access_token
from app.models.run import RunStatus
from app.models.user import User
from app.schemas.codex import CodexSessionEventsResponse, CodexSessionRead
from app.schemas.run import RunCreate, RunEventListResponse, RunListResponse, RunRead
from app.services.auth_service import AuthService
from app.services.run_service import RunService

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=RunListResponse)
def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: RunStatus | None = Query(default=None, alias="status"),
    repo_filter: str | None = Query(default=None, alias="repo", min_length=1, max_length=511),
    user: User = Depends(get_current_user),
    service: RunService = Depends(get_run_service),
) -> RunListResponse:
    """Return runs owned by the current user."""
    return service.list_runs(
        current_user=user,
        limit=limit,
        offset=offset,
        status_filter=status_filter,
        repo_full_name=repo_filter,
    )


@router.post("", response_model=RunRead, status_code=status.HTTP_201_CREATED)
def create_run(
    payload: RunCreate,
    user: User = Depends(get_current_user),
    service: RunService = Depends(get_run_service),
) -> RunRead:
    """Create one run and prepare its workspace plus Codex bundle."""
    return service.create_run(payload, user)


@router.get("/{run_id}", response_model=RunRead)
def get_run(
    run_id: UUID,
    user: User = Depends(get_current_user),
    service: RunService = Depends(get_run_service),
) -> RunRead:
    """Return one run owned by the current user."""
    return service.get_run(run_id, user)


@router.get("/{run_id}/events", response_model=RunEventListResponse)
def list_run_events(
    run_id: UUID,
    user: User = Depends(get_current_user),
    service: RunService = Depends(get_run_service),
) -> RunEventListResponse:
    """Return ordered events for one run owned by the current user."""
    return service.list_run_events(run_id, user)


@router.post("/{run_id}/cancel", response_model=RunRead)
def cancel_run(
    run_id: UUID,
    user: User = Depends(get_current_user),
    service: RunService = Depends(get_run_service),
) -> RunRead:
    """Cancel one running host-side Codex session."""
    return service.cancel_run(run_id, user)


@router.get("/{run_id}/terminal/session", response_model=CodexSessionRead)
def get_run_terminal_session(
    run_id: UUID,
    user: User = Depends(get_current_user),
    service: RunService = Depends(get_run_service),
) -> CodexSessionRead:
    """Return current terminal session metadata for one run."""
    return service.get_terminal_session(run_id, user)


@router.get("/{run_id}/terminal/events", response_model=CodexSessionEventsResponse)
def get_run_terminal_events(
    run_id: UUID,
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    service: RunService = Depends(get_run_service),
) -> CodexSessionEventsResponse:
    """Return incremental terminal output for one run."""
    return service.get_terminal_events(run_id, offset=offset, current_user=user)


@router.websocket("/{run_id}/terminal")
async def stream_run_terminal(
    websocket: WebSocket,
    run_id: UUID,
    service: RunService = Depends(get_run_service),
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    """Stream terminal output for one run by polling the host executor."""
    token = websocket.query_params.get("token")
    user_id = decode_access_token(token) if token else None
    if user_id is None:
        await websocket.close(code=4401, reason="Unauthorized")
        return

    user = auth_service.get_user_by_id(user_id)
    if user is None:
        await websocket.close(code=4401, reason="Unauthorized")
        return

    try:
        service.get_run(run_id, user)
    except Exception:
        await websocket.close(code=4403, reason="Forbidden")
        return

    await websocket.accept()
    offset = 0

    try:
        while True:
            payload = service.get_terminal_events(run_id, offset=offset, current_user=user)
            for item in payload.items:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "output",
                            "offset": item.offset,
                            "text": item.text,
                            "created_at": item.created_at,
                        }
                    )
                )
            if payload.next_offset != offset:
                offset = payload.next_offset

            status_value = payload.session.status
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "status",
                        "status": status_value,
                        "exit_code": payload.session.exit_code,
                        "summary_text": payload.session.summary_text,
                        "error_message": payload.session.error_message,
                    }
                )
            )
            if status_value in {"completed", "failed", "cancelled"}:
                break
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return
