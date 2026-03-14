# Contributing

Thanks for contributing to Team Agent Platform.

This repository is an execution-first monorepo for running Codex-powered agent teams against real GitHub repositories. The project is still evolving quickly, so small, coherent, reviewable contributions are preferred over broad rewrites.

## Before you start

Read these files first:

1. [README.md](README.md)
2. [Architecture Overview](docs/architecture-overview.md)
3. [Run Resume and Recovery](docs/run-resume-recovery-plan.md) if your change touches recovery, resume, or host-executor behavior
4. [Live-Fire Validation Plan](docs/live-fire-validation-plan.md) if your change touches validation or operator workflows

## Development setup

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

The platform expects local host access to:

- `git`
- `gh`
- `codex`

Both `gh` and `codex` should already be authenticated under the same OS user that starts the host executor.

## Repository structure

- `apps/backend` — FastAPI backend
- `apps/web` — Next.js frontend
- `apps/host-executor` — host-side execution bridge
- `docs` — architecture and operational docs
- `infra` — local infrastructure
- `scripts` — developer automation

## Contribution guidelines

- Keep changes small and focused.
- Prefer explicit, maintainable code over clever abstractions.
- Avoid introducing distributed or enterprise patterns without a strong reason.
- Keep backend business logic out of route handlers.
- Keep public documentation in English.
- Keep code comments and docstrings in English.

## Validation

Run the checks that match your change.

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

If you only change documentation, a lighter validation pass is acceptable.

## Pull requests

When opening a PR:

- explain the user-visible goal;
- mention the main files changed;
- list the validation commands you ran;
- call out any known gaps or follow-up work.

If your change affects run lifecycle, recovery, or observability, include screenshots or terminal evidence when useful.
