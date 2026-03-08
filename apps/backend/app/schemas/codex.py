"""Schemas for backend Codex terminal proxy endpoints."""

from typing import Literal

from pydantic import BaseModel, Field

CodexSessionStatus = Literal["running", "completed", "failed", "cancelled"]


class CodexSessionStart(BaseModel):
    """Payload for starting one Codex session through the host executor."""

    run_id: str = Field(min_length=1, max_length=64)
    workspace_id: str = Field(min_length=1, max_length=64)
    prompt_text: str = Field(min_length=1, max_length=50_000)
    model: str | None = Field(default=None, min_length=1, max_length=128)
    model_reasoning_effort: Literal["low", "medium", "high"] | None = None
    sandbox_mode: Literal["read-only", "workspace-write", "danger-full-access"] = "workspace-write"


class CodexSessionRead(BaseModel):
    """Current host-side Codex session state."""

    run_id: str
    workspace_id: str
    repo_path: str
    command: list[str] = Field(default_factory=list)
    status: CodexSessionStatus
    pid: int | None = None
    exit_code: int | None = None
    error_message: str | None = None
    summary_text: str | None = None
    started_at: str
    finished_at: str | None = None
    last_output_offset: int = 0


class CodexTerminalChunk(BaseModel):
    """One raw terminal output chunk from Codex."""

    offset: int = Field(ge=0)
    text: str
    created_at: str


class CodexSessionEventsResponse(BaseModel):
    """Incremental terminal chunk response."""

    session: CodexSessionRead
    items: list[CodexTerminalChunk] = Field(default_factory=list)
    next_offset: int = 0
