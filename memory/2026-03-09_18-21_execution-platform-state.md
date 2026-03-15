# Memory

- Created at: 2026-03-09 18:21 MSK
- Topic: current execution platform state

## What is already working

- Host diagnostics page
- GitHub repo browsing through host `gh`
- Issue browsing and tracker mutations
- PR browsing
- Workspace lifecycle:
  - clone
  - branch
  - commit
  - push
  - draft PR
- Run lifecycle:
  - create run
  - clone repo
  - load repo execution config
  - run setup commands
  - materialize `.codex` and `TASK.md`
  - launch host-side `codex exec`
  - stream terminal
  - run checks
  - commit
  - push
  - create draft PR

## Important repo contract

File:

- `.team-agent-platform.toml`

Current purpose:

- declare setup commands
- declare check commands
- keep run bootstrap predictable

Important adjustments that were made:

- backend setup uses a PyPI mirror fallback:
  - `PIP_INDEX_URL=${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}`
- `make compose-config` was hardened to work with:
  - `docker`
  - `podman-compose`
  - `podman`

## Host executor operational notes

- After reboot, `host executor` must be started explicitly.
- Backend and frontend containers can be alive while host executor is down.
- If diagnostics show `Connection refused` for `:8765`, the host executor is not running.

Working launch mode used in this session:

```bash
export HOST_EXECUTOR_RELOAD=0
export PIP_INDEX_URL='https://pypi.tuna.tsinghua.edu.cn/simple'
./scripts/dev/run-host-executor.sh
```

Reason:

- `--reload` is avoided to reduce lost session state during active runs.
- mirror env works around local DNS issues for `pypi.org`

## Important users in local DB

- `platform-owner@team-agent-platform.local`
  - display name: `Команда платформы`
  - password: `platform-owner-123`
- `demo@team-agent-platform.local`
  - display name: `Platform Demo`

Important note:

- runs page shows only runs owned by the currently signed-in user
- most real runs in this session were created by `Команда платформы`

## Reusable team state

Published agent profiles:

- `delivery-orchestrator`
- `backend-platform-engineer`
- `frontend-product-engineer`

Published team:

- `fullstack-delivery-squad`
- Russian title: `Команда fullstack-разработки`

## Reliability fixes already merged

- long host workspace commands now use a dedicated long timeout
- cleanup of materialized files is idempotent enough for missing generated files
- host-friendly compose validation is available

## Resume hints

Check these first before launching or debugging a run:

1. `http://127.0.0.1:3000/diagnostics`
2. `http://127.0.0.1:8000/api/v1/host/readiness`
3. `.team-agent-platform.toml`
4. signed-in user on `/runs`
