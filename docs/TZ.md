Отлично. Тогда фиксируем стек так:

* **Backend:** FastAPI
* **Frontend:** **Next.js + TypeScript**
* **UI-компоненты:** **shadcn/ui + Tailwind CSS**
* **БД:** PostgreSQL
* **Кэш / очереди:** Redis
* **ORM:** SQLAlchemy 2.0
* **Миграции:** Alembic
* **Фоновые задачи:** Celery или Dramatiq
* **Хранилище файлов:** S3-compatible
* **Auth:** JWT + OAuth GitHub
* **Поиск:** PostgreSQL FTS/trigram на MVP

Ниже даю уже **нормальное ТЗ под разработку MVP**.

---

# ТЗ на MVP

## Проект: маркетплейс субагентов и команд агентов

## 1. Цель проекта

Разработать веб-платформу, на которой пользователи смогут:

* публиковать субагентов для coding-экосистем;
* собирать субагентов в команды;
* искать и фильтровать агентов;
* экспортировать агентов и команды под разные рантаймы;
* оставлять оценки, отзывы и комментарии;
* видеть совместимость, версии и уровень доверия к агенту.

---

# 2. Технологический стек

## Backend

* FastAPI
* SQLAlchemy 2.0
* Alembic
* PostgreSQL
* Redis
* Celery / Dramatiq
* Pydantic v2
* S3-compatible storage
* JWT auth
* GitHub OAuth

## Frontend

* Next.js
* TypeScript
* Tailwind CSS
* shadcn/ui
* React Hook Form
* Zod
* TanStack Query
* Zustand
* lucide-react

## DevOps / Infra

* Docker Compose для локальной разработки
* Nginx / Traefik
* GitHub Actions или GitLab CI
* Sentry
* Prometheus/Grafana опционально позже

---

# 3. Роли пользователей

## Гость

* просмотр каталога;
* поиск;
* просмотр карточек агентов и команд;
* просмотр рейтингов и отзывов.

## Автор

* создание и редактирование профиля;
* публикация агентов;
* публикация команд;
* загрузка артефактов;
* выпуск новых версий;
* просмотр статистики своих сущностей.

## Обычный пользователь

* избранное;
* оценки;
* комментарии/отзывы;
* создание собственных команд из публичных агентов;
* экспорт.

## Модератор / Админ

* просмотр жалоб;
* скрытие/архивация пакетов;
* верификация автора;
* верификация агента;
* управление featured-списками.

---

# 4. Основные сущности

## 4.1 Agent

Публикуемая сущность субагента.

Поля:

* id
* slug
* title
* short_description
* full_description
* category
* author_id
* icon_url
* repository_url
* documentation_url
* license
* status (`draft`, `published`, `archived`, `hidden`)
* verification_status (`none`, `validated`, `verified`)
* created_at
* updated_at

## 4.2 AgentVersion

Версия агента.

Поля:

* id
* agent_id
* version
* changelog
* manifest_json / manifest_yaml
* source_archive_url
* compatibility_matrix
* export_targets
* install_instructions
* published_at
* is_latest

## 4.3 Team

Команда агентов.

Поля:

* id
* slug
* title
* description
* author_id
* icon_url
* status
* created_at
* updated_at

## 4.4 TeamItem

Элемент внутри команды.

Поля:

* id
* team_id
* agent_version_id
* role_name
* order_index
* config_json
* is_required

## 4.5 Review

Оценка и отзыв.

Поля:

* id
* user_id
* entity_type (`agent`, `team`)
* entity_id
* rating
* text
* works_as_expected
* outdated_flag
* unsafe_flag
* created_at
* updated_at

## 4.6 ExportJob

Экспорт под конкретный runtime.

Поля:

* id
* entity_type
* entity_id
* runtime_target
* status
* result_url
* error_message
* created_by
* created_at

## 4.7 ValidationRun

Проверка публикации.

Поля:

* id
* entity_type
* entity_id
* version_id
* status
* report_json
* started_at
* finished_at

## 4.8 Favorite

Избранное пользователя.

## 4.9 Report

Жалоба на агента, команду или отзыв.

---

# 5. Функциональные требования

## 5.1 Каталог агентов

Система должна позволять:

* просматривать список агентов;
* искать по названию, slug, описанию, тегам;
* фильтровать по:

  * runtime,
  * категории,
  * языку,
  * verification status,
  * рейтингу,
  * свежести обновления;
* сортировать по:

  * популярности,
  * рейтингу,
  * новизне,
  * количеству экспортов.

## 5.2 Карточка агента

На странице агента должно отображаться:

* название;
* описание;
* автор;
* иконка;
* рейтинг;
* число отзывов;
* версии;
* совместимость;
* список поддерживаемых runtime;
* инструкция по использованию;
* changelog;
* trust badges;
* отзывы;
* кнопка “добавить в команду”;
* кнопка “экспорт”.

## 5.3 Публикация агента

Автор должен иметь возможность:

* создать черновик;
* заполнить метаданные;
* загрузить manifest;
* загрузить архив или ссылку на репозиторий;
* указать совместимость;
* отправить на валидацию;
* опубликовать;
* выпустить новую версию.

## 5.4 Конструктор команды агентов

Пользователь должен иметь возможность:

* создать команду;
* добавить в нее несколько агентов;
* указать роль каждого агента;
* указать порядок использования;
* сохранить команду;
* экспортировать как bundle.

## 5.5 Экспорт

Система должна поддерживать экспорт в:

* Codex
* Claude Code
* OpenCode

Для каждого экспорта система:

* валидирует совместимость;
* генерирует целевой пакет/архив/manifest;
* выдает файл или инструкцию установки.

## 5.6 Оценки и отзывы

Пользователь должен иметь возможность:

* поставить оценку от 1 до 5;
* оставить отзыв;
* отметить:

  * работает ли агент как заявлено;
  * устарел ли он;
  * есть ли подозрение на небезопасность.

## 5.7 Избранное

Пользователь может:

* добавлять агентов и команды в избранное;
* просматривать отдельный список избранного.

## 5.8 Модерация

Модератор должен иметь возможность:

* скрывать агента/команду;
* архивировать;
* ставить verified;
* просматривать жалобы;
* просматривать отчеты валидации.

---

# 6. Нефункциональные требования

* API должно поддерживать REST.
* Все публичные endpoints должны документироваться через OpenAPI.
* Время ответа каталога: p95 до 300–500 мс на MVP.
* Система должна поддерживать пагинацию.
* Загрузка файлов должна быть ограничена по типу и размеру.
* Все действия модерации должны логироваться.
* Должен быть rate limit на auth, reviews, exports.
* Ошибки должны быть стандартизированы.
* Критические действия должны покрываться audit log.

---

# 7. Архитектура backend

Я бы делал так:

```text
backend/
  app/
    api/
      v1/
        auth.py
        users.py
        authors.py
        agents.py
        agent_versions.py
        teams.py
        reviews.py
        exports.py
        favorites.py
        admin.py
    core/
      config.py
      security.py
      db.py
      redis.py
      exceptions.py
    models/
      user.py
      author_profile.py
      agent.py
      agent_version.py
      team.py
      team_item.py
      review.py
      favorite.py
      export_job.py
      validation_run.py
      report.py
    schemas/
      auth.py
      user.py
      author.py
      agent.py
      agent_version.py
      team.py
      review.py
      export.py
      common.py
    repositories/
      user.py
      agent.py
      agent_version.py
      team.py
      review.py
      export.py
    services/
      auth_service.py
      agent_service.py
      team_service.py
      export_service.py
      validation_service.py
      review_service.py
      moderation_service.py
    tasks/
      exports.py
      validations.py
    utils/
      slug.py
      pagination.py
      manifest.py
      adapters.py
    migrations/
  tests/
```

## Подход по слоям

* `api` — только маршруты и wiring
* `schemas` — Pydantic-схемы
* `models` — ORM
* `repositories` — доступ к БД
* `services` — бизнес-логика
* `tasks` — фоновые задачи
* `utils/adapters` — адаптеры экспорта под разные платформы

Это тебе подойдет, потому что проект быстро будет расти, и если свалить всё в routes + crud, потом будет боль.

---

# 8. Архитектура frontend

```text
frontend/
  src/
    app/
      (public)/
        page.tsx
        agents/
          page.tsx
          [slug]/
            page.tsx
        teams/
          page.tsx
          [slug]/
            page.tsx
        authors/
          [slug]/
            page.tsx
      dashboard/
        page.tsx
        agents/
          page.tsx
          new/
            page.tsx
          [slug]/
            edit/
              page.tsx
        teams/
          page.tsx
          new/
            page.tsx
        favorites/
          page.tsx
        settings/
          page.tsx
      admin/
        page.tsx
        reports/
          page.tsx
        moderation/
          page.tsx
    components/
      ui/
      layout/
      agents/
      teams/
      reviews/
      forms/
      shared/
    features/
      auth/
      agents/
      teams/
      exports/
      reviews/
      favorites/
      admin/
    lib/
      api/
      query/
      utils/
      constants/
      validators/
    hooks/
    store/
    types/
```

---

# 9. Набор UI-компонентов

Для твоего кейса **shadcn/ui** — правильный выбор.

## Базовые компоненты

* Button
* Input
* Textarea
* Badge
* Card
* Dialog
* Drawer
* Tabs
* Dropdown Menu
* Select
* Combobox
* Sheet
* Tooltip
* Pagination
* Skeleton
* Alert
* Toast
* Avatar

## Для каталога

* Search bar
* Filter sidebar
* Sort dropdown
* Agent card
* Team card
* Tag list
* Rating stars
* Compatibility badges

## Для публикации

* Multi-step form
* File upload area
* YAML/JSON editor
* Version editor
* Changelog form
* Validation result panel

## Для команд агентов

* drag-and-drop список агентов
* role selector
* order manager
* dependency warnings
* export modal

## Для админки

* moderation table
* reports table
* validation status viewer
* action confirmation dialog

---

# 10. Основные API endpoints

## Auth

```http
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/oauth/github
GET  /api/v1/me
```

## Agents

```http
GET    /api/v1/agents
POST   /api/v1/agents
GET    /api/v1/agents/{slug}
PATCH  /api/v1/agents/{slug}
DELETE /api/v1/agents/{slug}
POST   /api/v1/agents/{slug}/publish
POST   /api/v1/agents/{slug}/versions
GET    /api/v1/agents/{slug}/versions
GET    /api/v1/agents/{slug}/versions/{version}
POST   /api/v1/agents/{slug}/validate
```

## Teams

```http
GET    /api/v1/teams
POST   /api/v1/teams
GET    /api/v1/teams/{slug}
PATCH  /api/v1/teams/{slug}
DELETE /api/v1/teams/{slug}
POST   /api/v1/teams/{slug}/items
PATCH  /api/v1/teams/{slug}/items/{item_id}
DELETE /api/v1/teams/{slug}/items/{item_id}
POST   /api/v1/teams/{slug}/export
```

## Reviews

```http
GET    /api/v1/agents/{slug}/reviews
POST   /api/v1/agents/{slug}/reviews
GET    /api/v1/teams/{slug}/reviews
POST   /api/v1/teams/{slug}/reviews
POST   /api/v1/reviews/{id}/report
```

## Favorites

```http
GET    /api/v1/favorites
POST   /api/v1/favorites
DELETE /api/v1/favorites/{id}
```

## Exports

```http
POST   /api/v1/exports/agents/{slug}
POST   /api/v1/exports/teams/{slug}
GET    /api/v1/exports/{id}
```

## Admin

```http
GET    /api/v1/admin/reports
GET    /api/v1/admin/validations
POST   /api/v1/admin/agents/{id}/verify
POST   /api/v1/admin/agents/{id}/hide
POST   /api/v1/admin/teams/{id}/hide
```

---

# 11. Канонический manifest

Я бы задал внутренний формат `agentforge.yaml`.

Пример структуры:

```yaml
id: fastapi-reviewer
title: FastAPI Reviewer
type: subagent
version: 1.2.0
description: Reviews FastAPI architecture and API design
author:
  name: temirkhan
category: backend
tags:
  - fastapi
  - python
  - review
runtimes_supported:
  - codex
  - claude_code
  - opencode
entrypoints:
  - review_api_structure
instructions: |
  Analyze project structure, routers, schemas, services and repositories.
tools_required:
  - file_read
  - shell
permissions_required:
  - read_repo
export_targets:
  - codex
  - claude_code
  - opencode
repository_url: https://example.com/repo
license: MIT
```

---

# 12. Этапы разработки MVP

## Этап 1. Основа проекта

* инициализация backend и frontend;
* auth;
* базовая БД;
* публичный каталог;
* страница агента.

## Этап 2. Публикация

* кабинет автора;
* создание/редактирование агента;
* версии;
* загрузка manifest;
* публикация.

## Этап 3. Команды агентов

* создание команды;
* добавление агентов;
* порядок ролей;
* страница команды.

## Этап 4. Экспорт

* адаптеры под 3 runtime;
* генерация экспортов;
* скачивание результата.

## Этап 5. Социальный слой

* отзывы;
* рейтинги;
* избранное;
* базовые trust badges.

## Этап 6. Админка и валидация

* модерация;
* проверки;
* жалобы;
* verified status.

---

# 13. MVP backlog по приоритету

## P0

* регистрация/логин
* каталог агентов
* карточка агента
* создание агента
* версии
* публикация
* создание команды
* экспорт
* отзывы
* базовая модерация

## P1

* избранное
* профиль автора
* verification workflow
* статистика экспортов

## P2

* комментарии
* featured collections
* приватные команды
* организационные workspace

---

# 14. Моя рекомендация по фронту

Для такого проекта я бы не брал “голый React”.
Я бы сразу делал:

* **Next.js App Router**
* **TypeScript**
* **Tailwind**
* **shadcn/ui**
* **TanStack Query**
* **Zod**
* **React Hook Form**

Почему:

* каталог и SEO важны;
* нужен быстрый production-ready UI;
* shadcn/ui даст тебе готовые компоненты без ощущения “типовой админки”.

---

# 15. Жесткий вывод по реализации

Тебе не нужен сейчас перегруженный enterprise-монстр.
Тебе нужен **чистый MVP**, где уже видно 3 вещи:

* люди могут **опубликовать** агента;
* люди могут **собрать команду**;
* люди могут **экспортировать** под разные coding-рантаймы.
