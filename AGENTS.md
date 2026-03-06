# AGENTS.md

## Purpose

This repository contains a monorepo for an MVP marketplace of subagents and agent teams.

Agents working in this repository should help build, refactor, validate, and maintain the project according to the product and technical documentation in `docs/`.

## Source of truth

Always read these files first before making meaningful changes:

1. `docs/TZ.md`
2. `docs/PRD.md`

If there is a conflict:
- prefer `docs/TZ.md`
- then use `docs/PRD.md`
- then use the current codebase as implementation context

Do not duplicate product requirements in code comments or commit summaries unless necessary.

## Repository mode

This project must remain a **monorepo** in the initial stage.

Do not split the project into multiple repositories.
Do not introduce microservices unless explicitly requested.
Prefer a clean modular monorepo structure over premature decomposition.

## High-level stack

- Backend: FastAPI
- Frontend: Next.js + TypeScript
- UI: Tailwind CSS + shadcn/ui
- Database: PostgreSQL
- Cache / queue: Redis
- ORM: SQLAlchemy
- Migrations: Alembic
- Local environment: Docker Compose
- Container runtime for builds, checks, and test execution: Podman may be used freely

## Agent permissions and execution policy

You may inspect, create, edit, move, and delete files in the repository when needed for the task.

You may:
- read all repository files
- update configuration files
- install dependencies
- run formatters
- run linters
- run tests
- run builds
- run dev servers when needed for validation
- create or update containers
- use Podman for running commands, checks, builds, and local validation flows
- use shell commands needed to complete the task
- add missing project scaffolding if it is aligned with the documentation

Assume you have broad execution freedom inside the local development environment.

When useful, prefer reproducible command execution through scripts, Make targets, Docker Compose, or Podman commands.

## Podman policy

Podman is allowed and preferred whenever containerized execution is helpful.

Agents may use Podman to:
- build images
- run containers
- start local dependencies
- execute backend or frontend checks inside containers
- validate reproducible local setup
- run one-off scripts or test commands

If a task can be validated more reliably through Podman, do it.

## Working style

Before making changes:
1. Inspect the relevant files.
2. Understand the local context.
3. Check whether the requested behavior already exists.

When making changes:
- prefer small, coherent, reviewable changes
- preserve consistency with the existing architecture
- avoid unnecessary rewrites
- avoid speculative abstractions
- keep MVP scope tight
- keep naming clear and boring
- favor maintainability over cleverness

After making changes:
- run relevant checks
- fix obvious breakages introduced by your changes
- summarize what changed and what remains

## Architecture expectations

Keep the codebase modular and easy to evolve.

Expected top-level direction:
- `apps/` for runnable applications
- `packages/` for shared code if needed later
- `docs/` for product and technical documentation
- `infra/` for local infrastructure and deployment-related files
- `scripts/` for developer automation

Avoid introducing `packages/` too early unless there is real shared logic.

## Backend expectations

Backend should follow a layered structure where practical:
- API/router layer
- schemas
- services
- repositories
- models
- core/config

Avoid putting business logic directly into route handlers.

## Frontend expectations

Frontend should use:
- Next.js App Router
- TypeScript
- Tailwind
- shadcn/ui
- a clean feature-oriented structure where useful

Avoid overengineering the frontend state layer at the start.

## Documentation expectations

Keep documentation concise and current.

Update documentation when:
- commands change
- structure changes
- setup changes
- major architectural decisions change

Do not generate excessive documentation noise.

## Code quality rules

- Write clear code.
- Prefer explicitness over magic.
- Keep functions focused.
- Keep modules cohesive.
- Remove dead code when encountered and safe to remove.
- Add comments only when they clarify intent that is not obvious from the code.

## Language rules

- Code comments must be in English.
- Docstrings must be in English.
- User-facing product documentation may be in Russian.
- Keep identifiers in English.

## Scope control

This is an MVP-first repository.

Do not introduce:
- unnecessary event buses
- unnecessary CQRS
- unnecessary plugin systems
- unnecessary distributed abstractions
- unnecessary background complexity
- enterprise-only patterns before they are justified

Build the simplest system that correctly supports the documented MVP.

## If requirements are unclear

Do not invent large product behaviors.

Use this order:
1. `docs/TZ.md`
2. `docs/PRD.md`
3. existing implementation patterns
4. minimal pragmatic assumption

When assumptions are necessary, choose the smallest viable one and make progress.

## Preferred first steps in a fresh repository

If the repository is still at an early stage, prioritize:
1. monorepo skeleton
2. backend bootstrap
3. frontend bootstrap
4. local infrastructure
5. environment templates
6. root README
7. health checks
8. CI basics
9. MVP feature implementation

## Output expectations

When finishing a task, provide:
- a short summary of what was done
- the main files changed
- any commands used for validation
- the most logical next step