# ТЗ

## Статус

Дата обновления: 8 марта 2026.

Этот документ фиксирует техническое ТЗ под новый продуктовый вектор.
Старое направление "marketplace агентов и команд" больше не является целевым для MVP.

Новый целевой продукт:
- local-first;
- Codex-first;
- single-user;
- execution platform поверх host `codex`, `gh` и `git`.

## 1. Цель проекта

Разработать веб-платформу, в которой пользователь может:
- собрать команду агентов под свой workflow;
- выбрать GitHub-репозиторий и задачу;
- запустить Codex над проектом через локально установленный `codex` CLI;
- видеть live terminal выполнения в браузере;
- получить branch и draft PR через локально установленный `gh` CLI.

## 2. Базовые допущения MVP

MVP работает в режиме:
- `single-user`
- `self-hosted`
- `host tools available`

Это означает:
- `gh` уже установлен на машине пользователя;
- `gh auth login` уже выполнен пользователем;
- `codex` уже установлен на машине пользователя;
- `codex login` уже выполнен пользователем;
- `OPENAI_API_KEY` в первой итерации не требуется;
- backend/executor имеют доступ к тем же host tools в том же OS-user context.

В MVP не требуется:
- собственный GitHub OAuth flow;
- GitHub App;
- отдельный облачный runner fleet;
- API-key authentication для Codex внутри приложения;
- хранение GitHub/OpenAI credentials в БД приложения.

## 3. Архитектурная модель

Система делится на 2 логических слоя.

### 3.1 Control Plane

Слой приложения:
- frontend;
- backend API;
- хранение agent profiles, teams, runs, diagnostics snapshots.

Отвечает за:
- UI;
- команды агентов;
- запуск run;
- хранение статусов;
- WebSocket terminal bridge;
- отображение результатов.

### 3.2 Host Execution Layer

Локальный execution layer, который работает с host tools:
- `git`
- `gh`
- `codex`
- `pty`
- опционально `tmux` позже

На первой итерации это не отдельный cloud runner.
Это может быть:
- сам backend, если он запускается нативно на хосте;
- или отдельный localhost bridge/daemon, если backend остается в контейнере.

Технически это still execution component, но не отдельная облачная runner-подсистема.

## 4. Технологический стек

### Backend

- FastAPI
- SQLAlchemy 2.0
- Alembic
- PostgreSQL
- Redis
- Pydantic v2

### Frontend

- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui
- xterm.js для terminal UI

### Host execution

- `git`
- `gh`
- `codex`
- `pty`/PTY subprocess management
- WebSocket streaming
- `tmux` опционально позже, не обязателен для первой рабочей версии

### Локальная инфраструктура

- Docker Compose / Podman Compose для backend/frontend/database
- host-native execution для `gh` и `codex`

## 5. Основные сущности

### 5.1 AgentProfile

Локально управляемый профиль агента.

Поля:
- id
- slug
- title
- short_description
- full_description
- category
- status (`draft`, `published`, `archived`)
- codex_instructions
- skills
- markdown_files
- created_at
- updated_at

Примечание:
- agent profile больше не рассматривается как marketplace package;
- public versioning не входит в текущий MVP.

### 5.2 Team

Команда агентов.

Поля:
- id
- slug
- title
- description
- status (`draft`, `published`, `archived`)
- created_at
- updated_at

### 5.3 TeamItem

Элемент команды.

Поля:
- id
- team_id
- agent_profile_id
- role_name
- order_index
- config_json
- is_required

### 5.4 RepoTarget

Нормализованное описание GitHub repo, выбранного через `gh`.

Поля:
- provider (`github`)
- owner
- name
- default_branch
- is_private
- url

### 5.5 Run

Одна execution-сессия над repo и задачей.

Поля:
- id
- team_id
- repo_owner
- repo_name
- base_branch
- working_branch
- issue_number nullable
- task_text
- status
- started_at
- finished_at
- pr_url nullable
- summary_text nullable
- error_message nullable

### 5.6 RunEvent

События выполнения.

Поля:
- id
- run_id
- type
- message
- payload_json
- created_at

### 5.7 DiagnosticsSnapshot

Диагностика host environment.

Поля:
- id
- git_found
- git_version
- gh_found
- gh_version
- gh_auth_ok
- codex_found
- codex_version
- codex_auth_ok
- pty_supported
- warnings_json
- created_at

## 6. Функциональные требования

## 6.1 Diagnostics

Система должна уметь проверять и показывать пользователю:
- установлен ли `git`;
- установлен ли `gh`;
- установлен ли `codex`;
- версии `gh` и `codex`;
- выполнен ли `gh auth`;
- выполнен ли `codex login`;
- доступен ли запуск PTY-сессии;
- может ли текущий backend/executor использовать эти host tools.

Если что-то не так, система должна показывать:
- понятную причину;
- точный статус;
- шаги исправления.

Примеры сообщений:
- `gh not found`
- `gh is installed but not authenticated`
- `codex not found`
- `codex version is too old`
- `backend cannot access host codex binary`

## 6.2 Управление agent profiles

Система должна позволять:
- создавать agent profile;
- редактировать title, description, Codex instructions;
- добавлять skills;
- добавлять markdown files;
- публиковать draft profile для использования в командах.

На текущем этапе не требуется:
- публичный marketplace;
- рейтинги;
- отзывы;
- публичные версии;
- social catalog features.

## 6.3 Управление командами

Система должна позволять:
- создавать draft-команду;
- добавлять в нее опубликованные agent profiles;
- задавать `role_name`;
- задавать порядок;
- редактировать состав;
- публиковать команду.

### Правила публикации команды

- команда не должна быть пустой;
- `role_name` обязателен;
- `role_name` должен быть уникален внутри команды;
- `order_index` должен быть нормализован;
- использовать можно только опубликованные agent profiles.

## 6.4 GitHub Tracker adapter

Нужен adapter для работы с issues и смежными сущностями через `gh`.

Adapter должен вызывать `gh ... --json ...` и возвращать нормализованные структуры.

Поддерживаемые сценарии MVP:
- список repo;
- список issues;
- чтение issue;
- добавление комментария;
- чтение labels;
- добавление/удаление labels.

Где возможно, нужно использовать `--json`.
Если mutating команда не отдает готовый JSON-результат, adapter обязан:
- выполнить команду;
- затем сделать повторный `gh ... view --json ...`;
- вернуть нормализованный объект.

## 6.5 GitHub SCM adapter

Нужен adapter для работы с branch/PR/checks flow.

Принцип:
- git-операции через `git subprocess`;
- GitHub metadata операции через `gh subprocess`.

Поддерживаемые сценарии MVP:
- clone repo;
- checkout base branch;
- create working branch;
- commit changes;
- push branch;
- create draft PR;
- read PR metadata;
- read PR checks/status summary.

GitHub OAuth внутри приложения не требуется.
Источником доступа является уже авторизованный `gh` на машине пользователя.

## 6.6 Run creation

Пользователь должен иметь возможность создать run со следующими входными данными:
- team;
- repo;
- base branch;
- issue number или task text;
- optional title/summary override.

После создания run система должна перевести его в `queued`.

## 6.7 Run lifecycle

Поддерживаемые статусы:
- `queued`
- `preparing`
- `cloning_repo`
- `materializing_team`
- `starting_codex`
- `running`
- `committing`
- `pushing`
- `creating_pr`
- `completed`
- `failed`
- `cancelled`

## 6.8 Workspace preparation

Для каждого run система должна:
- создать отдельный workspace directory;
- клонировать repo;
- checkout `base_branch`;
- создать working branch;
- материализовать `.codex/` из выбранной команды;
- создать `TASK.md` с формулировкой задачи и ограничениями.

## 6.9 Codex execution

Codex должен запускаться как subprocess в отдельной PTY-сессии.

Требования:
- stdin/stdout/stderr прокидываются через backend/executor;
- frontend получает live stream через WebSocket;
- пользователь видит живой терминал в браузере;
- сессию можно завершить корректно;
- по завершении run сохраняется итоговый статус и summary.

На первом этапе допустимы два режима:
- интерактивный `codex` session;
- `codex exec` с live output stream.

PTY является обязательным минимумом.
`tmux` не обязателен в первой версии и может быть добавлен позже для reattach/persistence.

## 6.10 Итоговые git/GitHub действия

После успешного выполнения run система должна уметь:
- проверить наличие изменений;
- сделать commit;
- push working branch;
- создать draft PR через `gh pr create`.

В MVP не требуется:
- auto-merge;
- merge queue;
- auto-deploy;
- auto-close issue beyond standard PR references.

## 6.11 Live terminal

Во frontend должен быть terminal UI, который:
- показывает live output Codex run;
- поддерживает reconnect при кратковременном потере соединения;
- показывает текущий статус run;
- показывает итоговую summary и PR link.

## 7. Нефункциональные требования

### 7.1 Execution model

MVP рассчитан на одного пользователя и одну хост-машину.

Система не обязана поддерживать:
- multi-user concurrent execution;
- distributed runners;
- cloud isolation;
- enterprise RBAC.

### 7.2 Security model

Приложение не должно:
- хранить GitHub токены пользователя в БД;
- хранить OpenAI API keys пользователя в БД;
- реализовывать собственный secret vault для host CLI auth.

Источником доступа считаются:
- `gh auth`
- `codex login`

### 7.3 Diagnostics first

Ни один run не должен стартовать без preflight diagnostics.

Если окружение не готово, UI должен блокировать старт и показывать remediation steps.

### 7.4 Observability

Для каждого run нужно хранить:
- timestamps;
- status transitions;
- terminal output chunks;
- error message;
- итоговую summary;
- PR URL.

## 8. API-контур MVP

Ниже целевой API-контур для новой итерации.
Он является целевым контрактом, а не обещанием, что все endpoint уже реализованы.

### Diagnostics

- `GET /api/v1/host/diagnostics`
- `POST /api/v1/host/diagnostics/refresh`

### GitHub Tracker

- `GET /api/v1/github/repos`
- `GET /api/v1/github/repos/{owner}/{repo}/issues`
- `GET /api/v1/github/repos/{owner}/{repo}/issues/{number}`
- `POST /api/v1/github/repos/{owner}/{repo}/issues/{number}/comments`
- `POST /api/v1/github/repos/{owner}/{repo}/issues/{number}/labels`
- `DELETE /api/v1/github/repos/{owner}/{repo}/issues/{number}/labels/{name}`

### GitHub SCM

- `GET /api/v1/github/repos/{owner}/{repo}/pulls`
- `GET /api/v1/github/repos/{owner}/{repo}/pulls/{number}`
- `GET /api/v1/github/repos/{owner}/{repo}/pulls/{number}/checks`

### Agent profiles and teams

- `GET /api/v1/agents`
- `POST /api/v1/agents`
- `GET /api/v1/agents/{slug}`
- `PATCH /api/v1/agents/{slug}`
- `POST /api/v1/agents/{slug}/publish`
- `GET /api/v1/teams`
- `POST /api/v1/teams`
- `GET /api/v1/teams/{slug}`
- `PATCH /api/v1/teams/{slug}`
- `POST /api/v1/teams/{slug}/items`
- `PATCH /api/v1/teams/{slug}/items/{item_id}`
- `DELETE /api/v1/teams/{slug}/items/{item_id}`
- `POST /api/v1/teams/{slug}/publish`

### Runs

- `POST /api/v1/runs`
- `GET /api/v1/runs`
- `GET /api/v1/runs/{id}`
- `POST /api/v1/runs/{id}/cancel`
- `GET /api/v1/runs/{id}/events`
- `GET /api/v1/runs/{id}/artifacts`
- `WS /api/v1/runs/{id}/terminal`

## 9. Диагностика и fallback

Если `gh` не найден:
- показать шаг установки;
- не позволять запускать GitHub flow.

Если `gh` найден, но `gh auth` не выполнен:
- показать шаг `gh auth login`;
- не позволять стартовать run.

Если `codex` не найден:
- показать шаг установки;
- не позволять стартовать run.

Если `codex` найден, но login отсутствует:
- показать шаг входа;
- не позволять стартовать run.

Если версия `gh` или `codex` ниже минимальной:
- показать найденную версию;
- показать минимально поддерживаемую версию;
- показать команду обновления или ссылку на обновление.

## 10. Этапы реализации

### Этап 1

- обновить документацию;
- зафиксировать новую product рамку;
- добавить diagnostics layer.

### Этап 2

- реализовать GitHub Tracker adapter;
- реализовать GitHub SCM adapter;
- добавить Repo selection UI.

### Этап 3

- реализовать Run model и run lifecycle;
- реализовать PTY session manager;
- реализовать WebSocket terminal.

### Этап 4

- реализовать clone -> branch -> codex -> commit -> push -> draft PR;
- показать summary и PR URL в UI.

## 11. Финальное решение по направлению

На текущем этапе source of truth для продукта:

`Team Agent Platform = local-first Codex execution platform over GitHub repositories`

Все дальнейшие изменения кода, UI и архитектуры должны приниматься исходя из этой модели.
