# Runtime Boundary RFC

## Status

- Date: March 15, 2026
- Status: implemented baseline, with compatibility cleanup still pending
- Purpose: document the current multi-runtime architecture, reconcile the Claude Code backlog with the working tree, and define the remaining cleanup after the runtime-boundary refactor

## Backlog reconciliation

The current working tree now implements the Claude Code backlog end-to-end.

- `#30` runtime-neutral groundwork: implemented
- `#29` host-executor runtime, diagnostics, and resume flow: implemented
- `#27` export and workspace materialization: implemented
- `#28` UI, observability, and docs: implemented

Live-fire validation already confirmed:

- Claude Code runs can prepare workspaces, start runtime sessions, resume after interruption, and finalize into draft PRs
- Claude subagent execution is surfaced through structured execution-trace events
- the shared terminal/report UI can render both Codex and Claude Code runs

## Current state

The platform is no longer single-runtime in practice.

Today the codebase already supports:

- runtime-aware `Run` records and API payloads
- runtime-specific bundle materialization for Codex and Claude Code
- host-executor start, poll, cancel, and resume flows for both runtimes
- shared terminal/report UI that can render both runtimes
- runtime-aware readiness and diagnostics
- a shared host session engine for both runtimes
- runtime-specific execution-trace capture from terminal output

This means the system has already crossed the line from "Codex-only with experiments" to "multi-runtime with one shared execution architecture".

## What is already correct

The following architectural moves are correct and should be preserved:

- one shared run pipeline across workspace preparation, repo checks, commit, push, and PR creation
- runtime-specific bundle generation instead of forcing a single `.codex` contract
- a shared terminal contract for the UI instead of Codex-only terminal payloads
- one product model where `runtime_target` is part of the run context
- one backend adapter boundary for runtime-specific orchestration details
- one shared host session engine with runtime-specific strategy hooks

These are the right boundaries for an MVP monorepo. The platform does not need a plugin marketplace, microservices, or separate repositories.

## Main architectural debt

The current implementation is materially cleaner, but a few compatibility debts remain.

### 1. Session identity is still in compatibility mode

The run model now stores:

- `runtime_session_id` as the generic durable session identity
- `codex_session_id` as a backward-compatible Codex-specific mirror
- `claude_session_id` as a backward-compatible Claude-specific mirror

That is much better than the original Codex-only contract, but the model still carries legacy compatibility fields.

The boring generic contract is now:

- `runtime_session_id`
- `transport_kind`
- `transport_ref`
- `resume_attempt_count`
- `interrupted_at`

Legacy `codex_session_id` and `claude_session_id` should disappear only after older data and API consumers no longer rely on them.

### 2. Legacy run-status compatibility still exists

The runtime phase is now normalized around `starting_runtime` and report phase key `runtime`, but compatibility values still remain:

- `starting_codex` is still accepted and displayed correctly for old runs
- some UI components still explicitly map the legacy value for compatibility
- old event histories can still mention Codex-specific labels

This is correct for backward compatibility, but it should eventually collapse to the generic runtime vocabulary.

### 3. `RunService` still owns some runtime wording and compatibility mapping

`RunService` is now materially cleaner, and the adapter layer already owns:

- bundle materialization
- session start/resume/cancel/get-events
- terminal normalization
- runtime-specific audit extraction
- runtime-specific session identity payloads

The remaining runtime-specific concentration in `RunService` is mostly:

- user-facing note phrasing
- finalization/report wording
- persistence mapping around legacy compatibility fields

This is acceptable for two runtimes, but it is still the main place where additional runtimes would add friction.

### 4. Runtime-aware analytics are still event-oriented rather than first-class

Execution trace and recovery signals are now present in Activity, but they are still stored as event payloads rather than modeled as dedicated analytics tables or metrics.

That is fine for the MVP. It only becomes debt if the product needs historical aggregate analytics instead of run-level inspection.

## Target runtime boundary

The target architecture has four layers and is now mostly implemented.

### Shared run orchestration

The backend should own the run lifecycle that is common to every runtime:

- workspace preparation
- repo setup commands
- task handoff materialization
- status transitions
- repo checks
- commit, push, and draft PR creation

### Backend runtime adapter

Each runtime adapter should own:

- bundle materialization rules
- host session start/get-events/cancel/resume operations
- terminal normalization into the shared API contract
- runtime-specific audit extraction
- runtime-specific session identity extraction
- runtime-specific user-facing labels where needed

### Shared host session engine

The host executor should own a reusable runtime-neutral engine for:

- PTY/tmux launch and reconnect
- chunk storage
- background readers
- process interruption/cancellation
- durable recovery bookkeeping

### Runtime-specific host modules

Codex- and Claude-specific host modules should only own:

- command construction
- resume command construction
- runtime-specific session id extraction
- runtime-specific output parsing and summary/usage extraction

## Minimal interfaces

The backend runtime adapter boundary should stay intentionally small. The current implementation already follows this shape.

Suggested surface:

- `build_workspace_files(...)`
- `build_materialization_audit_payload(...)`
- `start_session(...)`
- `get_session(...)`
- `get_events(...)`
- `normalize_terminal_session(...)`
- `normalize_terminal_events(...)`
- `cancel_session(...)`
- `resume_session(...)`
- `build_session_identity_payload(...)`
- `build_note_session_payload(...)`

The host session engine should be runtime-neutral, while runtime modules provide strategy hooks such as:

- `build_start_command(...)`
- `build_resume_command(...)`
- `extract_runtime_session_id(...)`
- `parse_output_chunk(...)`
- `derive_summary_and_usage(...)`

## Remaining cleanup order

The remaining cleanup order is:

1. keep `runtime_session_id` as the primary session contract while carrying legacy mirrors for compatibility
2. continue shrinking runtime-specific wording in `RunService` where it makes reviews or new runtime support harder
3. remove legacy `starting_codex` handling once older runs no longer need to render it
4. keep docs aligned with the actual multi-runtime implementation
5. decide later whether run-level analytics need a stronger schema than event payloads

## Non-goals

This RFC does not propose:

- a plugin marketplace
- runtime packages split into separate repositories
- microservices
- support for arbitrary remote execution providers
- broad framework abstractions for more runtimes than the product actually needs

The goal is a boring, modular monorepo with a clean runtime boundary.
