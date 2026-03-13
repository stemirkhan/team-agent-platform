# План: Resume и Recovery для run-сессий

## Статус

- Дата: 11 марта 2026
- Статус: draft
- Цель документа: зафиксировать детальный план реализации recovery/resume для run-сессий после падения host executor

## 1. Контекст

Сейчас платформа умеет:

- создать workspace;
- materialize `.codex/` и `TASK.md`;
- запустить `codex exec` в host executor;
- стримить terminal output в UI;
- пройти setup/checks/commit/push/PR flow.

Но если host executor падает в момент активной Codex-сессии, run теряется как live execution unit:

- terminal state пропадает;
- backend трактует это как потерю session state;
- пользователю предлагается только relaunch / rerun;
- уже потраченные токены и накопленный контекст сессии практически не используются повторно.

Это особенно болезненно для длинных multi-step run-ов, где падение происходит после большого token burn, но до commit/push.

## 2. Проблема

Пользовательский сценарий:

1. run уже долго работает;
2. Codex потратил много токенов и успел сделать значимую работу;
3. host executor или runner-процесс падает;
4. после восстановления пользователь хочет не начинать заново, а продолжить тот же run.

Под "продолжить" здесь скрываются два разных уровня:

1. Продолжить тот же живой процесс.
2. Продолжить ту же Codex conversation/session, даже если старый процесс уже умер.

Это разные технические задачи, и их нельзя смешивать.

## 3. Цели

Нужный функционал должен позволять:

- не терять recoverable run после падения host executor;
- сохранить terminal history и контекст run;
- продолжить работу без полного relaunch;
- минимизировать повторный token burn;
- не создавать дублирующие Codex-процессы;
- оставить UX простым и предсказуемым.

## 4. Non-goals

В первую реализацию не входят:

- exact replay на том же git commit SHA;
- кросс-хост миграция run-сессий;
- автоматический recovery без пользовательского контроля во всех случаях;
- merge нескольких параллельно выживших/дублирующихся Codex-процессов;
- полноценный distributed runner orchestration.

## 5. Текущее состояние и ограничения

### 5.1 Что мешает resume сейчас

1. Codex запускается с `--ephemeral`.
   Это отключает native persistence session state, на который можно было бы опереться для `codex exec resume`.

2. Host executor привязывает Codex к обычному PTY child process.
   Если сам executor-процесс умирает, такой transport плохо переживает падение и не дает надежного reattach.

3. Persisted state в host executor хранит только:
   - публичный `session.json`;
   - terminal `chunks.jsonl`.

   Этого хватает для UI/history, но не для нативного продолжения Codex-сеанса.

4. После рестарта host executor текущая логика намеренно переводит interrupted running session в `failed`.

### 5.2 Вывод

В текущем MVP recovery невозможен не "случайно", а потому что реализация прямо сделана как non-resumable.

## 6. Два режима recovery

### 6.1 Transport recovery

Идея:

- Codex-процесс остается жив после падения host executor.
- После рестарта executor просто восстанавливает подключение к уже работающему process envelope.

Плюсы:

- минимальный дополнительный token burn;
- это почти настоящий "continue same process";
- пользователь не теряет прогресс.

Минусы:

- нужен более durable transport, чем текущий PTY child process;
- требуется контроль за orphan process и reconnect semantics.

### 6.2 Semantic resume

Идея:

- старый процесс умер;
- но Codex session/conversation сохранилась на диске;
- новый executor запускает `codex exec resume <session_id>`.

Плюсы:

- существенно лучше полного rerun;
- не требует, чтобы старый процесс продолжал жить;
- проще rollout, чем полноценный transport persistence.

Минусы:

- это не тот же процесс;
- некоторый дополнительный token burn все равно будет;
- нужно гарантировать, что Codex session id сохранен и доступен.

## 7. Рекомендуемая стратегия

Рекомендуем не пытаться сделать всё в одной версии.

### Рекомендуемый порядок

1. `V0 spike`
   Проверить локально и в коде точные свойства `codex exec resume`.

2. `V1 manual semantic resume`
   Дать пользователю возможность вручную продолжить interrupted run через `codex exec resume`.

3. `V2 durable transport via tmux`
   Добавить переживание падения executor без смерти самого Codex-процесса.

4. `V3 auto-recovery`
   Автоматически reattach/recover после рестарта host executor, но только после ввода надежных guardrails.

Это дает быстрый путь к полезному функционалу уже на `V1`, при этом не закрывает дорогу к "почти zero-loss" варианту на `V2`.

## 8. Архитектурное решение по фазам

### 8.1 V0 Spike

Нужно зафиксировать не предположения, а поведение реального CLI.

### Проверки spike

1. Убедиться, что `codex exec` без `--ephemeral` действительно пишет session files в `CODEX_HOME`.
2. Найти, где и как появляется `session_id`.
3. Проверить, работает ли `codex exec resume <session_id> --json` в том же repo.
4. Проверить, нужен ли дополнительный prompt для non-interactive resume.
5. Оценить, насколько resume увеличивает token usage относительно полного rerun.
6. Проверить, что перезапуск host executor не уничтожает workspace и `CODEX_HOME`.
7. Проверить, возможно ли без `tmux` сохранить живой process после смерти executor. Ожидание: нет или ненадежно.

### Результат spike

Должен появиться короткий engineering note с ответами:

- где лежит session id;
- какой минимальный набор файлов нужен для resume;
- нужен ли prompt;
- насколько реально опираться на native Codex resume;
- обязателен ли `tmux` для zero-loss recovery.

### 8.2 V1 Manual Semantic Resume

### Пользовательское поведение

Если host executor упал в момент `starting_codex` или `running`, и старый Codex process больше не жив, но session state Codex доступен, пользователь должен увидеть:

- статус `interrupted`;
- сообщение, что run recoverable;
- кнопку `Resume Codex session`.

После нажатия:

- стартует `codex exec resume`;
- тот же run продолжается, а не создается новый;
- в terminal history видна старая часть лога и новые chunks после recovery;
- UI показывает, что resume был начат.

### Почему продолжать тот же run, а не создавать новый

Для recovery это важнее, чем для rerun:

- пользователю нужен единый timeline;
- terminal history должна быть цельной;
- issue / task / branch контекст уже относится к этому run;
- отдельный новый run больше похож на `rerun`, а не на recovery.

### Изменения в модели данных

В `runs` добавить:

- `codex_session_id nullable`
- `resume_attempt_count int default 0`
- `interrupted_at nullable timestamptz`
- `transport_kind nullable string`
- `transport_ref nullable string`

Дополнительно расширить semantics `status`:

- `interrupted`
- `resuming`

Почему отдельные статусы нужны:

- `failed` означает terminal unrecoverable outcome;
- `interrupted` означает "run был прерван внешне, но возможно recoverable";
- `resuming` нужен, чтобы не давать повторный resume и не путать UI.

### Изменения в host executor

#### Команда запуска

Нужно перестать использовать `--ephemeral` для resumable run-ов.

Требование:

- per-run `CODEX_HOME` остается изолированным в workspace;
- Codex session files живут внутри этого `CODEX_HOME`;
- session persistence не утекает в глобальный `~/.codex`.

#### Сохранение session id

После старта Codex нужно:

1. найти session log в `codex-home/sessions/...`;
2. прочитать `session_meta`;
3. извлечь `payload.id`;
4. persist-нуть этот id в host executor state и затем в backend run.

Если session id не найден за разумное время:

- run остается non-resumable;
- recovery fallback невозможен;
- пользователь увидит обычный rerun path.

#### Recovery после рестарта executor

Вместо текущего жесткого перевода `running -> failed` нужно:

- загрузить persisted session state;
- проверить, жив ли старый process;
- если process умер, но `codex_session_id` существует, перевести session в recoverable interrupted state;
- не убивать process автоматически только из-за факта рестарта, пока не выполнена более точная проверка recovery strategy.

### Изменения в backend

Добавить:

- `POST /runs/{id}/resume`
- `RunService.resume_run(...)`

Backend должен:

1. проверить ownership;
2. проверить, что run в `interrupted`;
3. проверить, что у run есть `codex_session_id` и `workspace_id`;
4. перевести run в `resuming`;
5. вызвать host executor resume endpoint;
6. после успешного старта снова перевести run в `running`.

### Изменения в host-executor API

Добавить endpoint:

- `POST /codex/sessions/{run_id}/resume`

Он должен:

- проверить persisted state;
- убедиться, что сессия не running сейчас;
- запустить `codex exec resume <session_id> --json`;
- продолжить запись chunks в тот же persisted `chunks.jsonl`;
- увеличить `resume_attempt_count`.

### Resume prompt policy

Нужно протестировать два варианта:

1. Resume без prompt.
2. Resume с коротким системным prompt.

Предпочтительный fallback prompt:

`Host executor restarted. Continue the previous task from the current repository state. First inspect git status and pending work. Do not restart the task from scratch unless required.`

### Изменения во frontend

#### Run details

Для `interrupted` run:

- показывать warning, что host executor упал;
- показывать recoverable status;
- показывать кнопку `Resume Codex session`.

Для `resuming` run:

- отключать повторный resume;
- показывать status badge и progress message.

#### Run status badge

Добавить новые статусы:

- `interrupted`
- `resuming`

#### Terminal UI

Terminal panel уже умеет работать по offset-based chunk stream.
Это можно сохранить.

Нужно только:

- не очищать предыдущий terminal history;
- продолжать чтение из уже существующего `chunks.jsonl`;
- корректно показывать новую terminal phase после resume.

### Run events и observability

Добавить события:

- `codex_session_interrupted`
- `codex_resume_available`
- `codex_resume_requested`
- `codex_resume_started`
- `codex_resume_completed`
- `codex_resume_failed`

Эти события должны быть видны в Activity.

### 8.3 V2 Durable Transport через tmux

`V1` уже полезен, но все еще тратит дополнительные токены.
Чтобы реально "не потерять" активный Codex process, нужен durable transport.

### Почему именно tmux

Потому что `tmux`:

- живет отдельно от host executor process;
- позволяет reconnect;
- хорошо подходит для terminal-based workloads;
- уже упомянут в ТЗ как допустимое расширение для reattach/persistence.

### Как использовать tmux

Каждый run получает:

- `tmux` session name, например `tap-run-<run_id>`;
- один pane/window, в котором запускается `codex exec`.

Host executor должен:

- стартовать run внутри `tmux new-session -d`;
- забирать live output через `tmux pipe-pane` или регулярный `capture-pane`;
- persist-ить `transport_kind="tmux"` и `transport_ref=<session_name>`.

### Recovery semantics

Если host executor падает:

- `tmux` session остается жить;
- новый executor после рестарта проверяет `tmux has-session`;
- если session существует, run не должен считаться failed/interrupted;
- UI должен снова получать live output из того же live process.

### Важная граница

`tmux` нужен для transport recovery.
Он не заменяет `codex exec resume`.

Если `tmux` session умерла, но Codex conversation сохранена, нужен `V1` fallback.

### 8.4 V3 Auto-Recovery

Только после `V1` и `V2`.

### Автоматически можно делать только два безопасных сценария

1. `tmux` session всё еще жива:
   просто reattach без пользовательского вопроса.

2. session мертва, но есть resumable Codex session:
   лучше сначала оставить manual resume.

Причина:

- auto-resume может случайно создать дублирующую активность;
- у пользователя может быть желание сначала посмотреть workspace;
- late-stage steps могут иметь side effects.

Итог:

- `tmux reattach` можно auto;
- `codex exec resume` лучше manual хотя бы в первой реализации.

## 9. Предлагаемая state machine

Новые статусы run:

- `interrupted`
- `resuming`

### Разрешенные переходы

- `starting_codex -> running`
- `running -> interrupted`
- `interrupted -> resuming`
- `resuming -> running`
- `resuming -> failed`
- `interrupted -> failed`
- `interrupted -> cancelled`

### Что НЕ делать

- не переводить interrupted сразу в `failed`, если есть resume path;
- не разрешать `resume` из `completed`, `failed`, `cancelled`;
- не разрешать повторный `resume`, если уже `resuming`.

## 10. Изменения в API

### Backend API

- `POST /api/v1/runs/{run_id}/resume`

Response:

- тот же `RunRead`, обновленный после старта recovery

Ошибки:

- `404` run not found
- `409` run is not resumable
- `409` resume already in progress
- `503` host executor recovery failed

### Host executor API

- `POST /codex/sessions/{run_id}/resume`

Response:

- `CodexSessionRead`

## 11. Изменения в схеме данных

Минимальный набор новых полей в `Run`:

- `codex_session_id: str | None`
- `transport_kind: str | None`
- `transport_ref: str | None`
- `resume_attempt_count: int`
- `interrupted_at: datetime | None`

Почему не хранить это только в `runtime_config_json`:

- эти поля нужны для runtime decisions;
- нужны для UI;
- нужны для observability;
- по ним полезно фильтровать и дебажить.

## 12. Изменения в терминальном хранилище

Сейчас host executor пишет:

- `session.json`
- `chunks.jsonl`

Это надо сохранить, но расширить.

### Нужно добавить

- источник transport (`pty` / `tmux`)
- `codex_session_id`
- `resume_attempt_count`
- `recovered_from_restart bool`

### Для `chunks.jsonl`

Опционально стоит добавить metadata per chunk:

- `attempt_index`

Это не обязательно для `V1`, но полезно для разборов long-lived run-ов.

## 13. Диагностика и readiness

Если `tmux` станет частью recovery story, diagnostics должны уметь показывать:

- установлен ли `tmux`;
- доступен ли он в PATH host executor;
- поддерживается ли durable transport mode.

Важно:

- отсутствие `tmux` не должно ломать базовый run flow;
- но должно отключать zero-loss recovery path.

## 14. UX-детали

### Run details page

Показывать:

- `Interrupted` badge
- причина interruption
- `Resume Codex session`
- `Run again`

То есть recovery и rerun должны существовать одновременно, но как разные actions.

### Тексты

Нужно различать:

- `Resume session`
- `Run again`

Это не одно и то же.

### Activity

Пользователь должен видеть timeline:

- Codex was interrupted because host executor restarted
- Session is resumable
- Resume was requested
- Resume started
- Resume completed / failed

## 15. Риски

### Риск 1: Duplicate process

Старый Codex process ещё жив, а новый recovery создаёт второй.

Mitigation:

- перед resume делать transport-level liveness check;
- при `tmux` использовать `has-session`;
- при direct pid recovery не опираться только на pid, если transport уже не тот.

### Риск 2: Resume без native session id

Если `codex_session_id` не был сохранен, `codex exec resume` невозможен.

Mitigation:

- явный `resumable=false`;
- UI не показывает resume;
- остается только rerun.

### Риск 3: Token burn при semantic resume

Даже успешный `codex exec resume` не бесплатен.

Mitigation:

- позиционировать `V1` как reduced-loss recovery;
- для near-zero-loss довести `tmux` transport.

### Риск 4: Сломанный terminal stream после resume

Mitigation:

- сохранять offset-based chunk append;
- не обнулять terminal history;
- покрыть тестами recovery + resumed output append.

### Риск 5: Cleanup слишком рано удаляет materialized files

Mitigation:

- cleanup не должен происходить для interrupted/resumable runs;
- cleanup только после terminal finalization path.

## 16. Acceptance criteria

### Для V1

- Если host executor упал во время `running`, run может перейти в `interrupted`, а не только в `failed`.
- Если у run есть `codex_session_id`, пользователь может нажать `Resume Codex session`.
- После resume terminal history сохраняется и дополняется.
- Run не создает новый workspace и не меняет `working_branch`.
- Activity показывает interruption и resume events.

### Для V2

- Если host executor упал, а `tmux` session жива, Codex процесс продолжает работать.
- После восстановления executor UI может reconnect-нуться к той же live session.
- В этом сценарии нет полного semantic resume и нет полного rerun.

## 17. Детальный backlog

### Phase 0

- spike: non-ephemeral `codex exec`
- spike: discover `session_id`
- spike: validate `codex exec resume`
- spike: validate `tmux` survival and reattach

### Phase 1

- migration для новых полей `runs`
- расширение `RunStatus`
- host executor: сохранить `codex_session_id`
- host executor: interrupted вместо forced failed при recoverable case
- backend: `resume_run`
- backend API: `POST /runs/{id}/resume`
- web API client: `resumeRun`
- web status badges
- web run details action
- tests: host executor service
- tests: backend run service/API

### Phase 2

- host diagnostics: `tmux`
- host executor: `tmux` transport
- reattach on restart
- terminal stream over durable transport
- tests: `tmux` lifecycle and reconnect

### Phase 3

- auto-reattach for live `tmux` session
- manual fallback for semantic resume
- UX polish and metrics

## 18. Рекомендуемый старт реализации

Рекомендуемый первый implementation slice:

1. провести `V0 spike`;
2. реализовать `V1 manual semantic resume`;
3. только потом входить в `tmux`.

Причина:

- `V1` уже даст большую пользовательскую ценность;
- кодовая сложность существенно меньше;
- можно валидировать UX recovery до транспортного усложнения.

## 19. Что будем считать успехом

Функционал можно считать успешным, если при падении host executor во время активного Codex run пользователь:

- не теряет terminal history;
- видит, recoverable ли run;
- может продолжить run, а не только перезапускать его;
- не вынужден заново платить полный token cost в большинстве recovery scenarios.

## 20. Основные file touchpoints для реализации

### Backend

- `apps/backend/app/models/run.py`
  Нужно расширить модель `Run` новыми полями recovery/resume.

- `apps/backend/app/schemas/run.py`
  Нужно расширить `RunStatus`, `RunRead` и добавить schema для resume action, если понадобится payload.

- `apps/backend/app/api/v1/runs.py`
  Нужно добавить `POST /runs/{run_id}/resume`.

- `apps/backend/app/services/run_service.py`
  Главная orchestration logic:
  - перевод в `interrupted`;
  - `resume_run`;
  - sync run state после recovery;
  - event emission.

- `apps/backend/app/repositories/run.py`
  Нужны CRUD-операции для новых полей и, возможно, удобные helper-методы для increment `resume_attempt_count`.

- `apps/backend/tests/test_runs_api.py`
  Основной слой API/service regression tests.

### Host executor

- `apps/host-executor/host_executor_app/schemas/codex.py`
  Нужно расширить публичную схему session state recovery metadata.

- `apps/host-executor/host_executor_app/services/codex_session_service.py`
  Основная точка изменений:
  - убрать non-resumable assumptions;
  - capture `codex_session_id`;
  - interrupted/recovery semantics;
  - later `tmux` transport.

- `apps/host-executor/host_executor_app/api/codex.py`
  Нужно добавить endpoint resume.

- `apps/host-executor/host_executor_app/services/host_diagnostics_service.py`
  На этапе `tmux` нужно добавить диагностику `tmux`.

- `apps/host-executor/tests/test_codex_session_service.py`
  Основные tests для interrupted/resume/tmux recovery logic.

### Web

- `apps/web/src/lib/api.ts`
  Нужен client method `resumeRun`.

- `apps/web/src/components/runs/run-status-badge.tsx`
  Нужно добавить статусы `interrupted` и `resuming`.

- `apps/web/src/components/runs/run-details-panel.tsx`
  Нужны:
  - кнопка `Resume Codex session`;
  - новые warning states;
  - timeline/event rendering для recovery.

- `apps/web/src/components/runs/run-terminal-panel.tsx`
  Нужно убедиться, что terminal history корректно дописывается после resume.

- `apps/web/src/components/projects/execution-board-panel.tsx`
  Если board показывает run status, нужно добавить новые badges/колонки или хотя бы корректную группировку новых статусов.

- `apps/web/src/components/runs/runs-list-panel.tsx`
  Если status filters завязаны на фиксированный набор статусов, нужно обновить фильтрацию и подписи.

### Infra / docs

- Alembic migration для новых полей `runs`
- `docs/TZ.md`
  После реализации нужно обновить раздел про `tmux` и persistence.
- `docs/PRD.md`
  После реализации нужно явно отразить resumable execution flow.
