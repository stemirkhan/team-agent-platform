# Agent Marketplace Monorepo

MVP монорепозиторий маркетплейса для субагентов и команд агентов.

Главные требования и продуктовый контекст:
- `docs/TZ.md`
- `docs/PRD.md`

## Текущая структура

- `apps/backend` — FastAPI + SQLAlchemy + Alembic
- `apps/web` — Next.js + TypeScript + Tailwind + shadcn/ui base
- `docs` — продуктовая и техническая документация
- `infra` — Docker Compose и инфраструктурные заготовки
- `scripts` — скрипты локальной разработки

## Что уже реализовано

Foundation:
- монорепо-каркас с backend/frontend приложениями;
- локальный стек в `docker-compose`: PostgreSQL, Redis, backend, web;
- базовая конфигурация окружения через `.env`.

Первый MVP-срез:
- backend health-check: `GET /healthz` и `GET /api/v1/health`;
- auth API:
  - `POST /api/v1/auth/register`
  - `POST /api/v1/auth/login`
  - `GET /api/v1/me` (Bearer token)
  - `GET /api/v1/me/teams` (Bearer token)
- каталог агентов API:
  - `GET /api/v1/agents`
  - `GET /api/v1/agents/{slug}`
  - `POST /api/v1/agents` (Bearer token)
  - `POST /api/v1/agents/{slug}/publish` (Bearer token, owner only)
- каталог и конструктор команд API:
  - `GET /api/v1/teams`
  - `GET /api/v1/teams/{slug}`
  - `POST /api/v1/teams` (Bearer token)
  - `POST /api/v1/teams/{slug}/items` (Bearer token, owner only)
  - `POST /api/v1/teams/{slug}/publish` (Bearer token, owner only)
- frontend:
  - главная страница;
  - страницы авторизации `/auth/login` и `/auth/register`;
  - страница каталога `/agents`;
  - страница создания агента `/agents/new`;
  - страница агента `/agents/[slug]` с Add To Team (выбор из `моих draft-команд` + поиск);
  - страница каталога `/teams`;
  - страница создания команды `/teams/new`;
  - страница команды `/teams/[slug]` с базовым Team Builder (add item + publish).

## Быстрый старт

1. Создать `.env`:

```bash
cp .env.example .env
```

2. Поднять весь стек:

```bash
./scripts/dev/up.sh
```

3. Открыть:
- frontend: `http://localhost:3000`
- backend docs: `http://localhost:8000/docs`

4. Остановить стек:

```bash
./scripts/dev/down.sh
```

Если запускаешь из VS Code (Snap) и вручную используешь `podman-compose`, запускай с:

```bash
XDG_DATA_HOME=$HOME/.local/share podman-compose -f infra/compose/docker-compose.yml up -d --build
```

## Локальная проверка

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
```

Проверка compose-конфига:

```bash
make compose-config
```
