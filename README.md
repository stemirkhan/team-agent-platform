# Team Agent Platform

Team Agent Platform is a local-first execution platform for running Codex-powered agent teams against real GitHub repositories.

The project is intentionally opinionated:

- `Codex-first`
- `local-first`
- `single-user / self-hosted`
- `host tools driven`

It is not a hosted agent marketplace, a public catalog, or a social discovery product. The current product focus is execution: diagnostics, repository selection, issue/task input, live terminal visibility, and branch/PR delivery.

## What the platform does

With the current platform you can:

- define agent profiles and combine them into teams;
- select a GitHub repository and base branch;
- launch a run from an issue or a manual task;
- materialize a `.codex` bundle and `TASK.md` inside a prepared workspace;
- run `codex`, `git`, and `gh` through a host-side execution layer;
- watch terminal output and run events in the browser;
- create a branch, push it, and open a draft PR;
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
   - `gh` CLI
   - `git`
   - PTY / `tmux`
   - local workspaces

The browser talks to the backend. The backend orchestrates runs and stores state. The host executor runs in the host user context, where `git`, `gh`, and `codex` are already installed and authenticated.

See:

- [Architecture Overview](docs/architecture-overview.md)
- [Run Resume and Recovery](docs/run-resume-recovery-plan.md)
- [Live-Fire Validation Plan](docs/live-fire-validation-plan.md)
- [Contributing](CONTRIBUTING.md)

## Repository layout

- `apps/backend` — FastAPI, SQLAlchemy, Alembic
- `apps/web` — Next.js, TypeScript, Tailwind, shadcn/ui
- `apps/host-executor` — host-side execution bridge for `codex`, `gh`, `git`, PTY, and `tmux`
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
```

Minimum expectations:

- `git` is installed
- `gh` is installed and already authenticated
- `codex` is installed and already authenticated
- the host executor runs under the same OS user that owns those CLI sessions

## Quick start

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
4. materialize `.codex` and `TASK.md`;
5. start Codex in the host execution layer;
6. stream terminal output and run events;
7. run repository checks;
8. create a commit;
9. push the branch;
10. create a draft PR.

If the host executor or transport is interrupted, the platform supports resume and auto-recovery for recoverable sessions.

## Current status

The platform already includes:

- diagnostics for `git`, `gh`, `codex`, and host readiness;
- agent profile and team management;
- GitHub repository, issue, and PR browsing through `gh`;
- run history and run details;
- live terminal output;
- workspace lifecycle and draft PR creation;
- multi-agent bundle materialization;
- run resume and recovery via persisted Codex sessions and `tmux`.

## Open-source direction

This repository is being prepared for open development.

That means:

- public-facing documentation should be in English;
- product and architecture intent should live in versioned docs inside the repository;
- historical internal notes may remain in `memory/`, but current guidance should come from this README and the docs listed above.

## License

This project is released under the [MIT License](LICENSE).
