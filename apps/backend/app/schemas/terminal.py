"""Runtime-neutral terminal session schemas."""

from typing import Literal

from pydantic import BaseModel, Field

from app.models.export_job import RuntimeTarget

TerminalSessionStatus = Literal[
    "running",
    "resuming",
    "interrupted",
    "completed",
    "failed",
    "cancelled",
]


class TerminalSessionRead(BaseModel):
    """Current host-side terminal session state for one run."""

    runtime_target: RuntimeTarget
    run_id: str
    workspace_id: str
    repo_path: str
    command: list[str] = Field(default_factory=list)
    status: TerminalSessionStatus
    pid: int | None = None
    exit_code: int | None = None
    error_message: str | None = None
    summary_text: str | None = None
    runtime_session_id: str | None = None
    codex_session_id: str | None = None
    claude_session_id: str | None = None
    transport_kind: Literal["pty", "tmux"] = "pty"
    transport_ref: str | None = None
    resume_attempt_count: int = 0
    interrupted_at: str | None = None
    resumable: bool = False
    recovered_from_restart: bool = False
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    total_input_tokens: int | None = None
    total_output_tokens: int | None = None
    total_cache_creation_input_tokens: int | None = None
    total_cache_read_input_tokens: int | None = None
    total_cost_usd: float | None = None
    started_at: str
    finished_at: str | None = None
    last_output_offset: int = 0


class TerminalChunk(BaseModel):
    """One raw terminal output chunk from a host-side runtime session."""

    offset: int = Field(ge=0)
    text: str
    created_at: str


class TerminalSessionEventsResponse(BaseModel):
    """Incremental terminal chunk response for one runtime session."""

    session: TerminalSessionRead
    items: list[TerminalChunk] = Field(default_factory=list)
    next_offset: int = 0
