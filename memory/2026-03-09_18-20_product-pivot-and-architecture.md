# Memory

- Created at: 2026-03-09 18:20 MSK
- Topic: product pivot and target architecture

## Summary

The project pivoted away from the original public catalog direction.
The current MVP is a local-first, Codex-first, single-user execution platform over host `git`, `gh`, and `codex`.

## Current product model

- `docs/TZ.md` is the primary technical source of truth.
- `docs/PRD.md` is the secondary product source of truth.
- The platform is no longer optimized around public discovery, ratings, reviews, or catalog growth.
- The core workflow is:
  1. define reusable agent profiles
  2. assemble them into a team
  3. pick a GitHub repo and issue/task
  4. run Codex through host execution
  5. watch live terminal
  6. get branch and draft PR

## Architecture that was chosen

- Control plane:
  - `apps/backend`
  - `apps/web`
- Host execution layer:
  - `apps/host-executor`
- Local infra:
  - Postgres
  - Redis
  - Podman/Docker Compose stack for backend/frontend/db
- Host-native tools used by the executor:
  - `git`
  - `gh`
  - `codex`

## Important product constraints

- Single-user
- Self-hosted
- Host tools already installed and authenticated
- No `OPENAI_API_KEY` flow inside the product for MVP
- GitHub auth comes from host `gh`
- Codex auth comes from host `codex login`

## Important implementation consequences

- `runs` are user-owned, not global.
- Diagnostics are host-executor-centric.
- Repo execution is driven by `.team-agent-platform.toml`.
- Real runs are expected to be reproducible from repo contract + team composition.

## Resume hints

When continuing work in this repo, prefer tasks that improve:

- run reliability
- host execution observability
- repo execution contracts
- team quality and reuse
- run review UX
