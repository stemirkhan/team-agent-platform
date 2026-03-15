# Run Resume and Recovery

## Status

- Date: March 15, 2026
- Status: implemented, with follow-up polish still pending
- Purpose: document the current recovery architecture for interrupted runs and the work that remains

This document still uses some Codex-heavy examples because recovery work started there first.
The current codebase supports analogous Claude Code interruption and resume flows under the runtime-neutral boundary described in [Runtime Boundary RFC](runtime-boundary-rfc.md).

## Current implementation status

- `V0 spike`: effectively completed in code and live validation
- `V1 manual semantic resume`: completed
- `V2 durable transport via tmux`: completed
- `V3 auto-recovery`: completed

## What already works

- Codex no longer runs in a non-resumable `--ephemeral` mode for resumable flows.
- Runs store runtime session metadata including `runtime_session_id`, `resume_attempt_count`, `interrupted_at`, `transport_kind`, and `transport_ref`.
- `codex_session_id` and `claude_session_id` remain in the run model temporarily for backward compatibility with older recovery data and runtime-specific APIs.
- A run can move into `interrupted` instead of always becoming `failed`.
- The backend exposes `POST /runs/{id}/resume`.
- The UI exposes runtime-specific resume actions for resumable interrupted runs.
- The host executor supports runtime-specific resume commands for both Codex and Claude Code.
- `tmux` is used as the durable transport layer.
- If a `tmux` session survives a host-executor restart, the platform can reattach without a full rerun.
- If transport is lost but a durable runtime session id was captured, the host executor can perform semantic resume automatically.
- Diagnostics expose `tmux` readiness and runtime-aware tool readiness.
- Activity and execution trace show the multi-agent bundle, startup prompt usage, confirmed sub-agent signals, and recovery events.

## What is not finished yet

- A dedicated engineering note for the original `V0` spike has not been published.
- Some lifecycle edges around interrupted runs, resume behavior, and cleanup still need polish.
- Recovery-specific telemetry and metrics are not yet modeled as a first-class analytics layer.
- Resume and rerun semantics still need additional UX and product polish for a few edge cases.

## Context

The platform can:

- create a workspace;
- materialize a runtime bundle plus `TASK.md`;
- launch the selected runtime through the host executor;
- stream terminal output to the UI;
- clean runtime scaffolding, commit, push, and draft PR steps.

The original problem was straightforward:

1. a run could spend a large number of tokens before finishing;
2. the host executor could crash while Codex was still running;
3. the platform would lose the session as a live execution unit;
4. the only option was effectively a relaunch, wasting work and tokens.

Recovery was painful specifically because long runs could fail after significant progress but before commit or push.

## Problem statement

Users needed to recover a run that had already done meaningful work.

There are two distinct kinds of “continue”:

1. continue the same live process;
2. continue the same runtime conversation or session even if the original process died.

Those are different technical problems and must be treated separately.

## Goals

The recovery layer should:

- preserve recoverable runs after host-executor failure;
- keep terminal history and run context available;
- continue execution without a full relaunch whenever possible;
- minimize repeated token burn;
- avoid duplicate runtime processes;
- keep the UX predictable.

## Non-goals

The recovery system does not currently aim to provide:

- exact replay on the original git SHA;
- cross-host migration of active run sessions;
- fully autonomous recovery in every scenario;
- reconciliation of multiple surviving duplicate runtime processes;
- distributed runner orchestration.

## The two recovery modes

### 1. Transport recovery

The Codex process stays alive after the host executor dies.

After restart, the executor reconnects to the still-running process envelope.

Benefits:

- minimal additional token burn;
- closest thing to “continue the same process”;
- no need to ask Codex to reconstruct context.

Costs:

- requires a durable transport;
- requires reconnect logic and orphan-process guardrails.

### 2. Semantic resume

The original process is dead, but the runtime session survives on disk.

After restart, the executor launches:

```bash
codex exec resume <session_id>
```

For Claude Code, the equivalent flow uses the persisted Claude session id and the runtime's native resume flag.

Benefits:

- much better than a full rerun;
- does not require the original process to survive.

Costs:

- it is not the same live process;
- some additional token burn is still possible;
- the session id and session files must have been preserved correctly.

## Why recovery used to be impossible

At the start of the work, the platform was effectively non-resumable because:

1. Codex was launched with `--ephemeral`.
2. The executor relied on a plain PTY child process.
3. Persisted session state was good enough for UI history, but not for native Codex resume.
4. After restart, stale running sessions were forced into `failed`.

Those constraints are no longer the base state of the system.

## Recommended architecture

The implemented architecture follows this sequence:

1. validate real Codex resume behavior;
2. add manual semantic resume;
3. add durable transport with `tmux`;
4. add auto-recovery on top of those primitives.

This produces useful recovery already at `V1`, while preserving a path to near-zero-loss recovery with `tmux`.

## Current architecture by phase

### V0: spike

The spike answered the operational questions:

- where session state lives;
- how `codex exec resume` behaves;
- whether prompt injection is needed for resume;
- whether `tmux` is required for durable transport.

### V1: manual semantic resume

User-visible behavior:

- a recoverable run can enter `interrupted`;
- the UI exposes `Resume Codex session`;
- the backend triggers `codex exec resume`;
- terminal history stays attached to the same run instead of creating a new one.

### V2: durable transport via tmux

User-visible behavior:

- Codex can continue running even if the host executor restarts;
- if the `tmux` session survives, the executor can reattach and keep the run alive;
- this reduces the need for semantic resume.

### V3: auto-recovery

User-visible behavior:

- after host-executor restart, the platform first tries transport recovery;
- if transport is gone but a resumable Codex session exists, the platform can auto-start semantic resume;
- Activity records recovery-specific events.

## Current user-facing states

The run lifecycle now distinguishes:

- `running`
- `resuming`
- `interrupted`
- `failed`
- `cancelled`
- `completed`

This matters because `interrupted` is not equivalent to `failed`.

It means:

- the original run was disrupted;
- recovery may still be possible;
- the next correct operator action is not always “start over”.

## Recovery signals and observability

The platform currently surfaces:

- host and `tmux` readiness in diagnostics;
- persisted runtime session ids;
- auto-recovery events in `Activity`;
- structured sub-agent signals from collaboration tool calls;
- bundle snapshots that prove which startup prompt and multi-agent configuration were materialized.

Recent cleanup removed heuristic observability from the main execution trace. Only structured evidence is now used for confirmed sub-agent signals.

## Remaining follow-up work

The recovery architecture works, but the following items still deserve follow-up:

1. interrupted-run UX polish
   - especially the relationship between `Resume` and `Run again`
2. recovery telemetry
   - success rate, time to recovery, reason categories
3. better checkpoint semantics
   - clearer handling around checks, commit, and push boundaries
4. an explicit engineering note for the original spike
5. continued validation on external repositories

## Validation scenarios

The implemented system should be validated against:

1. a normal successful run;
2. a host-executor restart while `tmux` transport is still alive;
3. a host-executor restart after transport loss, with semantic resume available;
4. a host-executor restart without a captured `runtime_session_id`;
5. cancellation during recovery or resume;
6. a completed run with preserved terminal history and audit events.

## Practical guidance

When debugging resume or recovery:

1. check `/diagnostics`;
2. check `/api/v1/host/readiness`;
3. inspect the run status in the UI;
4. inspect the run `Activity` events;
5. inspect the host executor session metadata and terminal chunks;
6. confirm whether the run is transport-recoverable, semantically resumable, or neither.

## Summary

The platform now supports both manual resume and automatic recovery for interrupted runs across Codex and Claude Code.

The core architecture is in place:

- persisted runtime session state;
- durable transport with `tmux`;
- manual semantic resume;
- automatic recovery after host-executor restart.

The remaining work is mostly polish, metrics, and edge-case refinement rather than foundational recovery implementation.
