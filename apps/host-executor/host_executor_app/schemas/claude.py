"""Schemas for host Claude Code sessions."""

from typing import Literal

from pydantic import BaseModel, Field

ClaudeSessionStatus = Literal[
    "running",
    "resuming",
    "interrupted",
    "completed",
    "failed",
    "cancelled",
]

ClaudePermissionMode = Literal[
    "acceptEdits",
    "bypassPermissions",
    "default",
    "dontAsk",
    "plan",
    "auto",
]


class ClaudeSessionStart(BaseModel):
    """Payload for starting one Claude Code session in a prepared workspace."""

    run_id: str = Field(min_length=1, max_length=64)
    workspace_id: str = Field(min_length=1, max_length=64)
    prompt_text: str = Field(min_length=1, max_length=50_000)
    model: str | None = Field(default=None, min_length=1, max_length=128)
    effort: Literal["low", "medium", "high"] | None = None
    permission_mode: ClaudePermissionMode = "bypassPermissions"


class ClaudeSessionRead(BaseModel):
    """Current state of one host-side Claude Code session."""

    run_id: str
    workspace_id: str
    repo_path: str
    command: list[str] = Field(default_factory=list)
    status: ClaudeSessionStatus
    pid: int | None = None
    exit_code: int | None = None
    error_message: str | None = None
    summary_text: str | None = None
    runtime_session_id: str | None = None
    claude_session_id: str | None = None
    transport_kind: Literal["pty", "tmux"] = "pty"
    transport_ref: str | None = None
    resume_attempt_count: int = 0
    interrupted_at: str | None = None
    resumable: bool = False
    recovered_from_restart: bool = False
    output_bytes_read: int = 0
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


class ClaudeTerminalChunk(BaseModel):
    """One raw terminal output chunk from a Claude Code session."""

    offset: int = Field(ge=0)
    text: str
    created_at: str


class ClaudeSessionEventsResponse(BaseModel):
    """Incremental terminal chunk response for one Claude session."""

    session: ClaudeSessionRead
    items: list[ClaudeTerminalChunk] = Field(default_factory=list)
    next_offset: int = 0
