Ниже даю рабочую версию: сначала краткий разбор рынка, потом PRD, потом стартовое ТЗ.

Я исхожу из того, что под **CloudCoda / OpenCoda** ты имеешь в виду прежде всего экосистемы **Claude Code / OpenCode / Codex**. Если потом захочешь, расширим это до Copilot Agents, Cursor и Gemini CLI.

## 1) Что сейчас есть на рынке

Рынок уже явно движется в сторону **агентов, сабагентов, skills/plugins и команд агентов**, а не просто “чатов для кода”.
OpenAI продвигает Codex как coding agent, у него есть `AGENTS.md`, multi-agent режим и Agent Skills как переносимый формат расширения. Anthropic развивает Claude Code с кастомными subagents, skills, plugins и поддержкой marketplace-источников. OpenCode тоже уже имеет primary agents и subagents как часть базовой модели работы. ([OpenAI Developers][1])

Параллельно появляются **горизонтальные каталоги**. Например, LobeHub позиционирует себя как marketplace skills, совместимый с Claude Code, Codex CLI и ChatGPT. Есть и крупные community-каталоги вроде SkillsMP, а в экосистеме Claude Code уже существуют как официальный marketplace/plugins-репозиторий, так и community-marketplaces на GitHub. ([lobehub.com][2])

Сильный сигнал рынка еще и в том, что GitHub в феврале 2026 года вывел **Claude и Codex в Agent HQ** и прямо делает ставку на выбор между агентами разных провайдеров внутри одного рабочего контура. Это подтверждает, что рынок идет к **multi-agent / multi-provider orchestration**, а не к одному монолитному ассистенту. ([The GitHub Blog][3])

При этом рынок грязный и рискованный. У открытых маркетплейсов agent extensions уже всплывают проблемы с качеством, копипастой, мусорными пакетами и безопасностью. Это значит, что победит не просто “каталог”, а **доверенный каталог с валидацией, репутацией, sandbox-проверками и понятной совместимостью**. ([Hugging Face][4])

### Вывод по рынку

Ниша **не пустая**, но еще **не закрыта нормальным продуктом**.

Что уже есть:

* каталоги skills/plugins;
* community-репозитории сабагентов;
* платформы, где можно подключать разных агентов;
* отдельные plugin marketplaces для Claude Code. ([GitHub][5])

Чего пока явно не хватает:

* нейтрального **marketplace именно для coding subagents и agent teams**;
* нормального **экспорта/импорта между рантаймами**;
* рейтингов, отзывов, verifications и тестовых прогонов;
* удобной сборки **команд из нескольких сабагентов** с профилями ролей и совместимостью;
* “App Store логики” для инженерных агентов: версии, changelog, зависимости, trust badges, quality gates.

Это уже не факт из одного источника, а моя **рыночная интерпретация** на основе того, как сейчас устроены Codex, Claude Code, OpenCode и существующие skills/plugin directories. ([OpenAI Developers][6])

---

# 2) PRD

## Название рабочее

**AgentForge Market**
Нормальное имя для MVP. Потом можно переименовать.

## Product vision

Платформа, где разработчики публикуют, находят, оценивают, экспортируют и собирают в команды **subagents / skills / agent bundles** для coding-агентов: Codex, Claude Code, OpenCode и далее других совместимых runtimes.

## Problem statement

Сегодня экосистема фрагментирована:

* агенты живут в GitHub-репах, gists, директориях и маркетплейсах;
* нет единого trust layer;
* нет унифицированной карточки совместимости;
* трудно собрать не одного агента, а **команду агентов**;
* экспорт между платформами либо отсутствует, либо ручной;
* качество пакетов непрозрачно.

## Target audience

1. **Solo developer**
   Хочет быстро ставить готовых сабагентов: reviewer, debugger, architect, test-writer.

2. **Tech lead / team lead**
   Хочет собирать стандартные команды агентов для своей команды и делиться ими.

3. **AI power users / agent builders**
   Хочет публиковать своих агентов, набивать репутацию, получать фидбек.

4. **Small dev teams / agencies**
   Хочет использовать curated bundles под типовые workflow: backend team, frontend team, QA team, startup MVP team.

## JTBD

* Найти подходящего сабагента под задачу.
* Проверить, совместим ли он с моим рантаймом.
* Установить или экспортировать его в один клик.
* Собрать несколько агентов в команду.
* Оценить качество по отзывам, верификации и тестам.
* Опубликовать своего агента и получать usage/reputation.

## Product principles

* **Cross-runtime first**
* **Trust before growth**
* **Teams, not only single agents**
* **Portable packaging**
* **Developer-native UX**
* **Open-ish standard with adapters**

## Scope v1

### Входит

* каталог subagents/skills/bundles;
* карточка агента;
* публикация;
* версионирование;
* рейтинги и отзывы;
* теги, поиск, фильтры;
* сборка команды из нескольких агентов;
* экспорт в форматы для Codex / Claude Code / OpenCode;
* trust signals: verified, tested, safe, popular;
* страница автора;
* базовая moderation/admin panel.

### Не входит в MVP

* встроенный запуск агентов в облаке;
* биллинг для pay-per-run;
* сложная enterprise RBAC-модель;
* marketplace для MCP servers как отдельный вертикальный продукт;
* revenue share и платные агенты;
* полноценный visual workflow builder.

## Core entities

* **Agent** — единица публикации: сабагент / skill / plugin-like package.
* **Bundle / Team** — набор агентов с ролями и рекомендованным сценарием использования.
* **Runtime Adapter** — экспорт в конкретный формат платформы.
* **Author** — создатель агента/команды.
* **Review / Rating**
* **Version / Release**
* **Verification Report**
* **Compatibility Matrix**

## User flows

### 1. Discovery

Пользователь открывает каталог → ищет “fastapi reviewer” → фильтрует по runtime=Codex, language=Python, verified=true → открывает карточку.

### 2. Install / Export

На карточке выбирает runtime:

* Export to Codex
* Export to Claude Code
* Export to OpenCode
  Скачивает bundle/archive или получает CLI-команду / git-based install snippet.

### 3. Team building

Пользователь выбирает 3–6 агентов → “Create Team” → задает название и описание → платформа собирает team manifest → экспортирует team bundle.

### 4. Publish

Автор заполняет форму → загружает manifest + инструкцию + иконку + примеры → проходит validation → публикует версию.

### 5. Review & trust

Пользователь ставит оценку, пишет отзыв, отмечает “works as advertised / broken / unsafe / outdated”.

## Key features MVP

### Каталог

* поиск;
* фильтры по runtime, языку, категории, уровню зрелости;
* сортировка по rating, installs, recent, verified.

### Карточка агента

* описание;
* use cases;
* поддерживаемые runtimes;
* формат экспорта;
* версия;
* changelog;
* автор;
* отзывы;
* trust badges;
* dependencies;
* required tools / MCP / permissions.

### Публикация

* web form и manifest upload;
* semantic versioning;
* draft / published / archived;
* automated lint/validation.

### Команды агентов

* конструктор команды;
* роли внутри команды;
* team manifest;
* рекомендации по порядку запуска;
* экспорт команды как bundle.

### Экспорт

* Codex package/export
* Claude Code package/export
* OpenCode package/export
* базовый neutral manifest как внутренний canonical format

### Репутация и доверие

* verified author;
* verified package;
* automated validation passed;
* community rating;
* usage/install counters;
* report abuse / report unsafe.

## Differentiation

Твой шанс не в том, чтобы сделать “еще один каталог”.
Твой шанс в четырех вещах:

1. **Команды агентов как first-class entity**
   Почти все начинают с одиночных agents/skills. Ты можешь строить рынок вокруг **agent teams**.

2. **Cross-runtime adapters**
   Один canonical manifest → экспорт в Claude Code / Codex / OpenCode.

3. **Trust layer**
   Sandbox checks, permission manifests, deterministic validation, signatures.

4. **Developer reputation graph**
   У автора есть профиль, история версий, adoption, качество релизов.

## Success metrics

### North Star

Количество **успешных экспортов / установок** агентов и команд в неделю.

### Product metrics

* MAU каталога
* количество опубликованных агентов
* количество опубликованных команд
* conversion: page view → export
* review rate
* share of verified packages
* retention авторов
* % broken/flagged packages
* median time to first export

## Risks

1. **Зоопарк форматов**
   У разных платформ быстро меняются требования.
   Решение: canonical internal schema + adapters layer.

2. **Плохое качество user-generated agents**
   Решение: validation, quality score, verification tiers.

3. **Безопасность**
   Решение: permission manifest, static scan, sandbox test, manual moderation for promoted listings.

4. **Хрупкость дистрибуции**
   Если платформа меняет API/формат, экспорт ломается.
   Решение: versioned exporters и compatibility tests.

5. **Слабая ликвидность маркетплейса на старте**
   Решение: начать с curated seed catalog и 20–50 собственных качественных агентов/команд.

## Rollout plan

### Phase 1

Curated catalog + publish + export + ratings

### Phase 2

Teams/bundles + verification + author profiles

### Phase 3

Usage analytics + paid placement + premium verified packs

---

# 3) Черновое ТЗ

## 3.1 Архитектура MVP

### Frontend

* Next.js / React
* Tailwind
* shadcn/ui
* SSR для SEO каталога
* клиентский search/filter UI

### Backend

* FastAPI
* PostgreSQL
* Redis
* SQLAlchemy
* Alembic
* Celery / Dramatiq / RQ для фоновых проверок
* S3-compatible storage для артефактов

### Search

На MVP можно начать с PostgreSQL full-text + trigram.
Elasticsearch/OpenSearch не нужен сразу.

### Auth

* email/password
* GitHub OAuth
* позже Google OAuth

### Infra

* Docker Compose для dev
* Kubernetes не нужен на первом этапе
* object storage для manifests/icons/archives

## 3.2 Модули системы

### Auth & Users

* регистрация
* логин
* OAuth
* профиль пользователя
* роль admin/moderator/user

### Authors

* публичный профиль
* список published agents/bundles
* reputation counters

### Agents

* CRUD агентов
* загрузка manifest
* загрузка icon/assets
* release management
* совместимость
* зависимости
* permissions metadata

### Bundles / Teams

* CRUD команды
* привязка нескольких агентов
* роли и порядок использования
* team manifest generation

### Reviews

* рейтинг 1–5
* текстовый отзыв
* флаги “works”, “outdated”, “unsafe”
* one review per user per version

### Export

* export to Codex
* export to Claude Code
* export to OpenCode
* archive generation
* install snippet generation

### Validation

* schema validation
* lint
* compatibility checks
* safety checks
* file integrity
* optional test-run in sandbox

### Moderation

* reports
* hide/unpublish
* mark verified
* featured listings

## 3.3 Канонический внутренний формат

Нужен свой **canonical manifest**, например `agentforge.yaml`.

Пример полей:

* id
* slug
* title
* description
* author
* type: subagent | skill | team
* category
* runtimes_supported
* source_format
* version
* entrypoints
* instructions
* tools_required
* permissions_required
* dependencies
* tags
* examples
* export_targets
* license
* repository_url
* verification_status

Идея правильная: **не хранить платформо-зависимый формат как главную сущность**.
Главная сущность — твой neutral schema. Экспорт — это производная.

## 3.4 Основные API endpoints

### Auth

* `POST /auth/register`
* `POST /auth/login`
* `POST /auth/oauth/github`
* `GET /me`

### Users / Authors

* `GET /authors/{slug}`
* `PATCH /me/profile`
* `GET /me/packages`

### Agents

* `GET /agents`
* `POST /agents`
* `GET /agents/{slug}`
* `PATCH /agents/{slug}`
* `POST /agents/{slug}/releases`
* `GET /agents/{slug}/versions/{version}`
* `POST /agents/{slug}/submit-for-validation`

### Teams

* `GET /teams`
* `POST /teams`
* `GET /teams/{slug}`
* `PATCH /teams/{slug}`
* `POST /teams/{slug}/items`
* `POST /teams/{slug}/export`

### Reviews

* `POST /agents/{slug}/reviews`
* `GET /agents/{slug}/reviews`
* `PATCH /reviews/{id}`
* `POST /reviews/{id}/report`

### Export

* `POST /exports/agent/{slug}`
* `POST /exports/team/{slug}`
* `GET /exports/{id}`

### Moderation

* `GET /admin/reports`
* `POST /admin/packages/{id}/verify`
* `POST /admin/packages/{id}/feature`
* `POST /admin/packages/{id}/hide`

## 3.5 База данных: основные таблицы

* `users`
* `author_profiles`
* `packages`
* `package_versions`
* `package_assets`
* `package_runtime_compatibility`
* `teams`
* `team_items`
* `reviews`
* `review_reports`
* `exports`
* `validation_runs`
* `moderation_actions`
* `tags`
* `package_tags`
* `favorites`

## 3.6 Бизнес-правила

* slug уникален.
* новая версия не может дублировать существующую версию пакета.
* отзыв привязан к версии или latest stable.
* unpublished package не попадает в public search.
* verified badge ставится только после validation + mod action.
* export доступен только для published versions.
* team export падает, если один из агентов несовместим с выбранным runtime.

## 3.7 Non-functional requirements

* API p95 < 300 ms для каталога без тяжелых фильтров
* экспорт пакета < 5 сек
* validation runs — асинхронно
* audit log для moderation actions
* rate limiting на reviews/auth/export
* antivirus/static checks для uploaded archives
* observability: Sentry + metrics + structured logs

## 3.8 MVP backlog

### Must have

* auth
* public catalog
* package page
* publish package
* versioning
* ratings/reviews
* team builder
* export adapters x3
* admin moderation
* validation pipeline basic

### Should have

* favorites
* featured collections
* author verification
* download/install analytics

### Could have

* comments/discussions
* follow authors
* curated starter packs
* API tokens
* private organization catalog

---

# 4) Жесткая оценка идеи

Идея **жизнеспособная**, но только если ты не будешь строить это как “еще один каталог json/yaml-файлов”.

Если делать правильно, твое ядро продукта должно быть таким:

**Marketplace = catalog + trust + portability + teams**

Если убрать хотя бы два из этих четырех, получится слабый проект.

Самый сильный MVP-путь:

1. сделать **neutral package format**;
2. сделать **экспорт в 3 рантайма**;
3. сделать **команды агентов**;
4. сверху накинуть **рейтинги + verification**.

Именно это отличит тебя от просто “GitHub-списка useful agents”.

---

# 5) Что я бы рекомендовал как MVP-рамку

Первая версия:

* только developer audience;
* только coding agents;
* только 3 runtime: Codex, Claude Code, OpenCode;
* только free public packages;
* только curated moderation;
* seed-каталог из 30–50 пакетов и 10–15 команд.

Потому что двусторонний маркетплейс без стартовой ликвидности умирает очень быстро.
