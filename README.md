# Team Agent Platform Monorepo

Монорепозиторий local-first платформы для запуска команд Codex над пользовательскими GitHub-репозиториями.

Текущий продуктовый фокус:
- не marketplace агентов;
- не публичный каталог и не social/discovery платформа;
- а рабочая среда, где пользователь:
  - собирает свои agent profiles и teams;
  - выбирает GitHub-репозиторий и задачу;
  - запускает Codex над проектом через локально установленный `codex` CLI;
  - использует локально настроенный `gh` CLI для веток, PR, issues и комментариев.

Главные документы:
- `docs/TZ.md`
- `docs/PRD.md`

Если код и документация расходятся, ориентироваться нужно на текущие `docs/TZ.md` и `docs/PRD.md`. Кодовая база сейчас находится в переходном состоянии после изначального marketplace-направления.

## Текущая продуктовая рамка

Целевой MVP:
- `Codex-first`
- `local-first`
- `single-user / self-hosted`
- `host tools driven`

Ключевая идея:
- backend и frontend дают control plane;
- выполнение задачи идет через host `codex`, `gh` и `git`;
- пользовательские креды не хранятся в приложении, а берутся из уже настроенных CLI-сессий пользователя;
- для Codex в первой итерации не используется `OPENAI_API_KEY`: ожидается уже выполненный browser login / ChatGPT subscription login в `codex`;
- в браузере пользователь видит диагностику окружения, живой терминал run-сессии, статус шагов и итоговый PR.

## Структура монорепозитория

- `apps/backend` — FastAPI + SQLAlchemy + Alembic
- `apps/web` — Next.js + TypeScript + Tailwind + shadcn/ui base
- `docs` — продуктовая и техническая документация
- `infra` — Docker Compose и инфраструктурные заготовки
- `scripts` — локальные dev-скрипты и сиды

## Что уже есть в кодовой базе

Фундамент:
- backend/frontend приложения в одной монорепе;
- локальный стек `PostgreSQL + Redis + backend + web` через Compose;
- auth, health checks, базовые CRUD-сценарии;
- модели agent profiles и teams;
- экспорт в `codex / claude_code / opencode`;
- UI для редактирования agent profiles и сборки команд;
- diagnostics для `git`, `gh`, `codex`;
- GitHub browser и tracker actions через host `gh`:
  - список репозиториев;
  - просмотр repo metadata;
  - список issues;
  - просмотр отдельного issue;
  - добавление комментариев в issue;
  - добавление и удаление labels;
  - список pull requests;
  - просмотр pull request metadata;
  - просмотр normalized checks summary.
- workspace lifecycle foundation через host `git` + `gh`:
  - prepare workspace (`clone + checkout base + create branch`);
  - inspect git status;
  - local commit;
  - push branch;
  - create draft PR.

Важно:
- часть текущей реализации still legacy от старой идеи marketplace;
- документация уже переведена на новый вектор: local Codex execution platform;
- следующие итерации должны смещать backend/frontend от catalog/export-only UX к `diagnostics + repo run + terminal + PR flow`.

## Целевые следующие блоки

- host diagnostics для `git`, `gh`, `codex`;
- GitHub SCM adapter (`branches`, `PR`, `checks`, `merge state`);
- workspace lifecycle UI поверх нового host workspace layer;
- запуск Codex в отдельной PTY-сессии;
- WebSocket terminal в браузере;
- run lifecycle и логи;
- branch + draft PR flow.

## Быстрый старт

1. Создать `.env`:

```bash
cp .env.example .env
```

2. Поднять стек:

```bash
./scripts/dev/up.sh
```

3. В отдельном терминале поднять host executor:

```bash
./scripts/setup/host-executor-local.sh
./scripts/dev/run-host-executor.sh
```

4. Открыть:
- frontend: `http://localhost:3000`
- backend docs: `http://localhost:8000/docs`
- diagnostics: `http://localhost:3000/diagnostics`
- repos: `http://localhost:3000/repos`
- example PR detail: `http://localhost:3000/repos/cli/cli/pulls/12870`

5. Остановить compose-стек:

```bash
./scripts/dev/down.sh
```

Если запускаешь вручную через `podman-compose` из окружения, где нужен явный `XDG_DATA_HOME`, используй:

```bash
XDG_DATA_HOME=$HOME/.local/share podman-compose -f infra/compose/docker-compose.yml up -d --build
```

Host executor работает отдельно от compose и должен быть запущен в host user-context, где уже доступны `gh auth` и `codex login`.
В compose-режиме backend-контейнер ходит к нему через `host.containers.internal`, поэтому bridge должен слушать `0.0.0.0`, а не только `127.0.0.1`.

## Локальные проверки

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

## Host tools для целевого MVP

Для следующей продуктовой итерации на хосте пользователя должны быть доступны:

```bash
git --version
gh --version
gh auth status
gh auth setup-git
codex --help
codex login status
```

Минимальное ожидание от окружения:
- `git` установлен;
- `gh` установлен и уже авторизован под пользователем;
- `gh auth setup-git` выполнен, если clone/push идут по HTTPS;
- `codex` установлен и уже авторизован под пользователем;
- host executor запускается в том же user-context, где доступны эти CLI-сессии.

## Repo Execution Config

Для стабилизации run flow репозиторий может хранить `.team-agent-platform.toml` в корне.

Минимальный контракт:

```toml
[run]
working_directory = "."

[setup]
commands = [
  "cd apps/backend && .venv/bin/python -m pip install -e '.[dev]'",
]

[checks]
commands = [
  "cd apps/backend && .venv/bin/python -m pytest -q",
]
```

Что делает платформа:
- читает config после clone;
- запускает `setup.commands` до старта Codex;
- встраивает `checks.commands` в `TASK.md`;
- запускает `checks.commands` после Codex и до `commit -> push -> draft PR`.

## Host Executor

Текущая архитектура:
- `backend` в compose — это control plane;
- `host executor` на `127.0.0.1:8765` — это execution layer;
- backend ходит к нему по `HOST_EXECUTOR_BASE_URL`;
- в compose по умолчанию используется `http://host.containers.internal:8765`.

Если `Host Executor` не поднят, `/diagnostics` честно покажет, что execution source недоступен, даже если сам backend жив.

## Сид демо-данных

```bash
./scripts/dev/reset-marketplace-demo.sh
```

Скрипт пока использует текущие модели agents/teams и нужен только для локальной демонстрации UI и export-среза. В следующих итерациях он должен быть адаптирован под новый execution-first сценарий.
