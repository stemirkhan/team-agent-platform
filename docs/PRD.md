# PRD

## Статус

Дата обновления: 8 марта 2026.

Этот документ фиксирует новый продуктовый вектор.
Старый вектор "marketplace агентов и команд" больше не является целевой моделью MVP.

Теперь продукт — это local-first платформа для запуска команд Codex над реальными GitHub-репозиториями пользователя.

## Название

Рабочее название остается: `Team Agent Platform`.

Название можно сохранить, но смысл продукта теперь другой:
- не маркетплейс;
- не discovery-платформа;
- не публичный каталог пользовательских пакетов;
- а control plane для agent teams, repo tasks и Codex execution.

## Product Vision

Дать разработчику интерфейс, в котором он может:
- собрать команду агентов под свой workflow;
- выбрать GitHub-репозиторий и задачу;
- запустить Codex над проектом в локально контролируемом окружении;
- наблюдать live terminal и progress;
- получить branch, diff и draft PR без ручной рутины.

## Problem Statement

Сегодня у power-user, который хочет применять multi-agent workflow к реальному репозиторию, есть несколько проблем:

- команды агентов существуют разрозненно и слабо структурированы;
- нет удобной оболочки над `codex` CLI для запуска повторяемых командных сценариев;
- нет единого UX для:
  - выбора команды,
  - выбора repo,
  - постановки задачи,
  - live terminal,
  - итогового PR;
- подключение к GitHub обычно завязано либо на ручную работу в терминале, либо на тяжелую интеграцию через GitHub App/OAuth;
- пользователю нужен быстрый, self-hosted и понятный путь, а не сразу облачная платформа с runner fleet.

## Product Thesis

Первый продуктовый удар должен быть не в публичный каталог, а в execution workflow:

- пользователь уже имеет доступ к своим repo;
- пользователь уже может быть авторизован в `gh`;
- пользователь уже может быть авторизован в `codex`;
- пользователь уже может использовать `codex` через browser login без отдельного `OPENAI_API_KEY`;
- значит можно построить тонкий orchestration layer поверх этих host tools и быстро получить рабочий end-to-end flow.

## Target User

### 1. Solo developer

Хочет запускать подготовленную команду агентов над своей задачей и не переключаться между CLI, GitHub и ручным менеджментом веток.

### 2. Founder / small team lead

Хочет иметь повторяемый workflow:
- backend specialist
- frontend specialist
- orchestrator

и гонять его по issue или product task.

### 3. AI-native engineer

Хочет строить свои команды агентов и использовать их как стандартный рабочий контур поверх разных репозиториев.

## What The Product Is Not

Продукт на текущем этапе не является:
- marketplace публичных агентов;
- social catalog с рейтингами и отзывами;
- hosted cloud runner platform;
- multi-tenant SaaS с выделенными sandbox workers;
- GitHub App-based enterprise automation layer.

## JTBD

Когда у меня есть задача в GitHub или просто текстовая engineering task, я хочу:
- выбрать подготовленную команду агентов;
- выбрать репозиторий и базовую ветку;
- запустить Codex над проектом;
- видеть, что именно происходит в live terminal;
- получить предсказуемый branch и draft PR;
- не настраивать заново auth, если у меня уже работают `gh` и `codex` на хосте.

## Product Principles

- `Codex-first`
- `Local-first`
- `Single-user first`
- `Host tools before cloud infrastructure`
- `Observable execution over black-box automation`
- `Small reliable workflow over big platform promises`

## Core User Flows

### 1. Diagnostics flow

Пользователь открывает страницу диагностики и сразу видит:
- найден ли `git`;
- найден ли `gh`;
- найден ли `codex`;
- подходит ли версия `gh`;
- подходит ли версия `codex`;
- авторизован ли `gh`;
- авторизован ли `codex`;
- может ли система работать в текущем host-context.

### 2. Team definition flow

Пользователь создает agent profiles и собирает их в team:
- backend specialist
- frontend specialist
- orchestrator

Команда хранит роли, инструкции и composition metadata.

### 3. Repo task flow

Пользователь:
- выбирает GitHub repo;
- выбирает base branch;
- опционально выбирает issue;
- или вручную вводит task;
- выбирает команду;
- нажимает `Run`.

### 4. Execution flow

Система:
- создает workspace;
- клонирует repo;
- создает branch;
- материализует `.codex/` под выбранную команду;
- создает `TASK.md`;
- запускает `codex` в отдельной PTY-сессии;
- стримит вывод в браузер;
- завершает run;
- пушит branch;
- создает draft PR.

### 5. Review flow

Пользователь видит:
- live terminal;
- статус run;
- итоговую summary;
- branch name;
- PR URL;
- ошибки диагностики или выполнения.

## MVP Scope

### In scope

- local-first execution mode;
- single-user host execution;
- agent profiles и teams;
- Codex-only execution;
- browser-based Codex auth через уже существующий `codex login`, без API key flow внутри приложения;
- GitHub integration через установленный у пользователя `gh` CLI;
- Git operations через `git` subprocess;
- live terminal через `PTY + WebSocket`;
- diagnostics UI;
- run history;
- draft PR creation.

### Out of scope

- hosted cloud runner;
- GitHub OAuth в приложении;
- GitHub App installation flow;
- multi-user tenancy;
- billing;
- moderation;
- публичный marketplace;
- рейтинги, отзывы, social discovery;
- auto-merge и auto-deploy.

## Core Product Objects

### Agent Profile

Описание одной роли для выполнения задач в Codex team.

Содержит:
- title;
- short description;
- full instructions;
- runtime-specific Codex instructions;
- skills;
- markdown attachments.

### Team

Набор agent profiles с ролями и порядком использования.

### Repo Target

Нормализованное представление GitHub-репозитория, выбранного пользователем через `gh`.

### Run

Одна execution-сессия над repo и task.

### Run Event / Terminal Stream

События статуса и live terminal output.

### Diagnostics Snapshot

Слепок состояния host tools и readiness окружения.

## Differentiation

Продукт отличается не каталогом, а execution UX:

1. команды агентов как first-class entity;
2. локальный запуск через уже настроенный `codex` и `gh`;
3. живой terminal UX в браузере;
4. branch + draft PR flow из одной точки;
5. минимальный операционный порог входа без GitHub App и облачного runner-а.

## Success Metrics

### North Star

Количество успешных run-сессий, завершившихся branch или draft PR.

### Product metrics

- diagnostics pass rate;
- run start -> run complete conversion;
- % runs with successful branch push;
- % runs with successful draft PR creation;
- median time from task start to PR;
- % runs aborted by tooling issues (`gh/codex missing`, auth missing, bad repo state);
- repeat run rate per user.

## Risks

### 1. Host dependency risk

Продукт зависит от состояния локального окружения пользователя.

Снижение риска:
- сильная diagnostics page;
- понятные remediation steps;
- жесткая проверка версий и auth до старта run.

### 2. CLI contract risk

`gh` и `codex` — это CLI, а не стабильный backend API продукта.

Снижение риска:
- thin adapters;
- version checks;
- нормализация JSON output;
- graceful fallback с понятной диагностикой.

### 3. Security and trust risk

Продукт работает через уже авторизованные host tools.

Снижение риска:
- single-user local-first model;
- не хранить токены в БД;
- запускать только в host user context;
- не обещать multi-user SaaS semantics в MVP.

### 4. Architecture transition risk

Текущая кодовая база частично унаследована от marketplace-идеи.

Снижение риска:
- принять документацию как новый source of truth;
- поэтапно убирать legacy catalog-first UX;
- не тащить старые product assumptions в новые решения.

## Product Rollout Plan

### Phase 1

- обновить документацию и требования;
- добавить diagnostics layer;
- подготовить GitHub adapters;
- подготовить PTY execution layer для Codex.

### Phase 2

- сделать first usable local run;
- materialize `.codex/` из команды;
- stream terminal в браузер;
- сохранять run status и summary;
- создавать draft PR.

### Phase 3

- добавить issue-driven launch;
- добавить отмену, retry и run history UX;
- добавить repo-level config file;
- улучшить policy/scoping по ролям команды.

## Product Decision

На данном этапе продукт официально переопределен как:

`Local-first Codex Team Execution Platform for GitHub repositories`

Все дальнейшие архитектурные и продуктовые решения должны приниматься из этой рамки.
