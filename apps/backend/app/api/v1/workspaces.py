"""Workspace lifecycle endpoints proxied through the host executor."""

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_current_operator_user
from app.core.config import get_settings
from app.schemas.workspace import (
    WorkspaceCommandsRun,
    WorkspaceCommandsRunResponse,
    WorkspaceCommit,
    WorkspaceListResponse,
    WorkspaceMaterialize,
    WorkspacePrepare,
    WorkspacePullRequestCreate,
    WorkspaceRead,
)
from app.services.workspace_proxy_service import WorkspaceProxyService, WorkspaceProxyServiceError

router = APIRouter(
    prefix="/workspaces",
    tags=["workspaces"],
    dependencies=[Depends(get_current_operator_user)],
)
workspace_proxy_service = WorkspaceProxyService(get_settings())


@router.get("", response_model=WorkspaceListResponse)
def list_workspaces() -> WorkspaceListResponse:
    """Return all persisted local workspaces for the current host context."""
    try:
        return workspace_proxy_service.list_workspaces()
    except WorkspaceProxyServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/prepare", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
def prepare_workspace(
    payload: WorkspacePrepare,
) -> WorkspaceRead:
    """Prepare a new local workspace by cloning a repo and creating a branch."""
    try:
        return workspace_proxy_service.prepare_workspace(payload)
    except WorkspaceProxyServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/{workspace_id}", response_model=WorkspaceRead)
def get_workspace(
    workspace_id: str = Path(min_length=1),
) -> WorkspaceRead:
    """Return one workspace with refreshed git state."""
    try:
        return workspace_proxy_service.get_workspace(workspace_id)
    except WorkspaceProxyServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{workspace_id}/commit", response_model=WorkspaceRead)
def commit_workspace(
    payload: WorkspaceCommit,
    workspace_id: str = Path(min_length=1),
) -> WorkspaceRead:
    """Commit local changes inside an existing workspace."""
    try:
        return workspace_proxy_service.commit_workspace(workspace_id, payload)
    except WorkspaceProxyServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{workspace_id}/materialize", response_model=WorkspaceRead)
def materialize_workspace(
    payload: WorkspaceMaterialize,
    workspace_id: str = Path(min_length=1),
) -> WorkspaceRead:
    """Write text files into an existing workspace repo."""
    try:
        return workspace_proxy_service.materialize_workspace(workspace_id, payload)
    except WorkspaceProxyServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{workspace_id}/cleanup", response_model=WorkspaceRead)
def cleanup_workspace(workspace_id: str = Path(min_length=1)) -> WorkspaceRead:
    """Restore or delete temporary run scaffolding inside an existing workspace repo."""
    try:
        return workspace_proxy_service.cleanup_workspace(workspace_id)
    except WorkspaceProxyServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{workspace_id}/commands", response_model=WorkspaceCommandsRunResponse)
def run_workspace_commands(
    payload: WorkspaceCommandsRun,
    workspace_id: str = Path(min_length=1),
) -> WorkspaceCommandsRunResponse:
    """Run sequential shell commands inside one prepared workspace."""
    try:
        return workspace_proxy_service.run_commands(workspace_id, payload)
    except WorkspaceProxyServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{workspace_id}/push", response_model=WorkspaceRead)
def push_workspace(workspace_id: str = Path(min_length=1)) -> WorkspaceRead:
    """Push the workspace branch to origin."""
    try:
        return workspace_proxy_service.push_workspace(workspace_id)
    except WorkspaceProxyServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{workspace_id}/pull-request", response_model=WorkspaceRead)
def create_workspace_pull_request(
    payload: WorkspacePullRequestCreate,
    workspace_id: str = Path(min_length=1),
) -> WorkspaceRead:
    """Create a draft or ready pull request from a pushed workspace branch."""
    try:
        return workspace_proxy_service.create_pull_request(workspace_id, payload)
    except WorkspaceProxyServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(workspace_id: str = Path(min_length=1)) -> None:
    """Delete a persisted workspace directory."""
    try:
        workspace_proxy_service.delete_workspace(workspace_id)
    except WorkspaceProxyServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
