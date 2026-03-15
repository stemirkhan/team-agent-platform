# Team Agent Platform

Team Agent Platform is a local-first execution platform for running agent teams against real GitHub repositories through host-installed coding runtimes.

The project is intentionally opinionated:

- `runtime-neutral execution for Codex and Claude Code`
- `local-first`
- `single-user / self-hosted`
- `host tools driven`

It is not a hosted agent marketplace, a public catalog, or a social discovery product. The current product focus is execution: diagnostics, repository selection, issue/task input, live terminal visibility, and branch/PR delivery.

## What the platform does

With the current platform you can:

- define agent profiles and combine them into teams;
- select a GitHub repository and base branch;
- launch a run from an issue or a manual task;
- materialize a runtime bundle and `TASK.md` inside a prepared workspace;
- run `codex` or `claude`, plus `git` and `gh`, through a host-side execution layer;
- watch terminal output and run events in the browser;
- require the runtime to finalize the branch, push it, and open the draft PR itself;
- recover interrupted runs through resume and auto-recovery flows.

## High-level architecture

The system has two main layers:

1. `Control Plane`
   - Next.js frontend
   - FastAPI backend
   - PostgreSQL
   - Redis

2. `Host Execution Layer`
   - Host Executor
   - `codex` CLI
   - `claude` CLI
   - `gh` CLI
   - `git`
   - PTY / `tmux`
   - local workspaces

The browser talks to the backend. The backend orchestrates runs and stores state. The host executor runs in the host user context, where `git`, `gh`, and the selected runtime CLI are already installed and authenticated.

See:

- [Architecture Overview](docs/architecture-overview.md)
- [Runtime Boundary RFC](docs/runtime-boundary-rfc.md)
- [Run Resume and Recovery](docs/run-resume-recovery-plan.md)
- [Live-Fire Validation Plan](docs/live-fire-validation-plan.md)
- [Contributing](CONTRIBUTING.md)

## Repository layout

- `apps/backend` — FastAPI, SQLAlchemy, Alembic
- `apps/web` — Next.js, TypeScript, Tailwind, shadcn/ui
- `apps/host-executor` — host-side execution bridge for `codex`, `claude`, `gh`, `git`, PTY, and `tmux`
- `docs` — architecture and operational documentation
- `infra` — local compose setup and infrastructure assets
- `scripts` — local development and operational scripts
- `memory` — historical engineering notes and internal memory files

## Requirements

The platform assumes these host tools are available:

```bash
git --version
gh --version
gh auth status
gh auth setup-git
codex --help
codex login status
claude --version
claude auth status
```

Minimum expectations:

- `git` is installed
- `gh` is installed and already authenticated
- at least one supported runtime CLI is installed and already authenticated
- the host executor runs under the same OS user that owns those CLI sessions

## Quick start

### Fastest way to launch everything

If you want a copy-paste startup flow, use:

```bash
cp .env.example .env
./scripts/dev/up.sh
./scripts/setup/host-executor-local.sh
tmux new-session -d -s tap-host-executor 'cd /absolute/path/to/team-agent-platform && HOST_EXECUTOR_RELOAD=0 ./scripts/dev/run-host-executor.sh'
```

Then open:

- frontend: `http://localhost:3000`
- backend docs: `http://localhost:8000/docs`
- diagnostics: `http://localhost:3000/diagnostics`
- runs: `http://localhost:3000/runs`

To stop everything:

```bash
tmux kill-session -t tap-host-executor || true
./scripts/dev/down.sh
```

If you want to inspect the host executor directly:

```bash
tmux attach -t tap-host-executor
```

1. Create a local environment file:

```bash
cp .env.example .env
```

2. Start the control plane:

```bash
./scripts/dev/up.sh
```

3. Start the host executor in a separate terminal:

```bash
./scripts/setup/host-executor-local.sh
./scripts/dev/run-host-executor.sh
```

4. Open the application:

- frontend: `http://localhost:3000`
- backend docs: `http://localhost:8000/docs`
- diagnostics: `http://localhost:3000/diagnostics`
- runs: `http://localhost:3000/runs`
- repositories: `http://localhost:3000/repos`

5. Stop the control plane:

```bash
./scripts/dev/down.sh
```

## Local validation

Backend:

```bash
cd apps/backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
python -m ruff check app tests
python -m pytest
```

Frontend:

```bash
cd apps/web
npm install
npm run lint
npm run build
```

## Run flow

At a high level, one run goes through these stages:

1. create a run from the UI;
2. prepare a workspace;
3. clone the repository and create a working branch;
4. materialize the runtime bundle and `TASK.md`;
5. start the selected runtime in the host execution layer;
6. stream terminal output and run events;
7. clean temporary runtime files from the workspace;
8. create a commit when the runtime produced repository changes;
9. require the runtime to finalize commit, push, and draft PR from the prepared workspace;
10. fail the run if the runtime exits without fully finishing SCM delivery.

If the host executor or transport is interrupted, the platform supports resume and auto-recovery for recoverable sessions.

## Current status

The platform already includes:

- runtime-aware diagnostics for `git`, `gh`, `codex`, `claude`, `tmux`, and host readiness;
- agent profile and team management;
- GitHub repository, issue, and PR browsing through `gh`;
- run history and run details;
- live terminal output;
- workspace lifecycle and draft PR creation;
- multi-agent bundle materialization for Codex and Claude Code;
- run resume and recovery via persisted runtime sessions and `tmux`;
- a shared host session engine with runtime-specific parsers and command builders;
- runtime execution traces for Codex collaboration calls and Claude Agent-tool subagents.

## Open-source direction

This repository is being prepared for open development.

That means:

- public-facing documentation should be in English;
- product and architecture intent should live in versioned docs inside the repository;
- historical internal notes may remain in `memory/`, but current guidance should come from this README and the docs listed above.

## License

This project is released under the [MIT License](LICENSE).
