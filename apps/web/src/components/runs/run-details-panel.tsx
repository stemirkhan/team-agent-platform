"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ExternalLink, Loader2, Square, RefreshCcw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { RunStatusBadge } from "@/components/runs/run-status-badge";
import { RunTerminalPanel } from "@/components/runs/run-terminal-panel";
import { Button } from "@/components/ui/button";
import {
  clearAccessToken,
  fetchCurrentUser,
  getAccessToken,
  type AuthUser
} from "@/lib/auth-client";
import {
  cancelRun,
  fetchRun,
  fetchRunEvents,
  fetchWorkspace,
  type Run,
  type RunEvent,
  type Workspace
} from "@/lib/api";
import { formatAuthLoading, t, type Locale } from "@/lib/i18n";

type RunDetailsPanelProps = {
  locale: Locale;
  runId: string;
};

const terminalStatuses = new Set<Run["status"]>(["completed", "failed", "cancelled"]);

function isTemporaryExecutionPath(path: string): boolean {
  return path === "TASK.md" || path === ".codex" || path.startsWith(".codex/") || path.startsWith("agents/");
}

function formatTimestamp(locale: Locale, value: string | null): string {
  if (!value) {
    return "-";
  }

  return new Date(value).toLocaleString(locale === "ru" ? "ru-RU" : "en-US", {
    dateStyle: "medium",
    timeStyle: "medium"
  });
}

function formatShortSha(value: string | null): string {
  if (!value) {
    return "-";
  }
  return value.slice(0, 7);
}

function extractEventMessage(event: RunEvent, locale: Locale): string {
  const payload = event.payload_json;
  if (payload && typeof payload.message === "string" && payload.message.length > 0) {
    return payload.message;
  }
  if (payload && typeof payload.detail === "string" && payload.detail.length > 0) {
    return payload.detail;
  }

  switch (event.event_type) {
    case "status":
      return t(locale, { ru: "Изменение статуса run.", en: "Run status transition." });
    case "error":
      return t(locale, { ru: "Ошибка выполнения run.", en: "Run execution error." });
    case "note":
      return t(locale, { ru: "Служебная заметка run.", en: "Run note." });
    default:
      return event.event_type;
  }
}

function tryExtractNestedMessage(value: string | null): string | null {
  if (!value) {
    return null;
  }

  const normalized = value.trim();
  if (!normalized) {
    return null;
  }

  const visited = new Set<string>();
  let current: unknown = normalized;

  while (typeof current === "string") {
    const text = current.trim();
    if (!text || visited.has(text)) {
      break;
    }
    visited.add(text);

    if (text.startsWith("{")) {
      try {
        current = JSON.parse(text);
        continue;
      } catch {
        return text;
      }
    }

    return text;
  }

  if (current && typeof current === "object") {
    const payload = current as Record<string, unknown>;
    if (typeof payload.error === "object" && payload.error !== null) {
      const nested = payload.error as Record<string, unknown>;
      if (typeof nested.message === "string" && nested.message.trim()) {
        return nested.message.trim();
      }
    }
    if (typeof payload.message === "string" && payload.message.trim()) {
      return tryExtractNestedMessage(payload.message);
    }
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail.trim();
    }
  }

  return normalized;
}

export function RunDetailsPanel({ locale, runId }: RunDetailsPanelProps) {
  const router = useRouter();

  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loadingUser, setLoadingUser] = useState(true);
  const [run, setRun] = useState<Run | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [loadingRun, setLoadingRun] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function resolveUser() {
      const currentToken = getAccessToken();
      if (!currentToken) {
        if (!cancelled) {
          setToken(null);
          setUser(null);
          setLoadingUser(false);
        }
        return;
      }

      if (!cancelled) {
        setToken(currentToken);
      }

      try {
        const currentUser = await fetchCurrentUser(currentToken);
        if (!cancelled) {
          setUser(currentUser);
        }
      } catch {
        clearAccessToken();
        if (!cancelled) {
          setToken(null);
          setUser(null);
        }
      } finally {
        if (!cancelled) {
          setLoadingUser(false);
        }
      }
    }

    void resolveUser();

    return () => {
      cancelled = true;
    };
  }, []);

  const loadRunData = useCallback(async () => {
    if (!token) {
      return;
    }

    const [runPayload, eventsPayload] = await Promise.all([
      fetchRun(runId, token),
      fetchRunEvents(runId, token)
    ]);
    const workspacePayload = runPayload.workspace_id
      ? await fetchWorkspace(runPayload.workspace_id, token).catch(() => null)
      : null;
    setRun(runPayload);
    setWorkspace(workspacePayload);
    setEvents(eventsPayload.items);
  }, [runId, token]);

  useEffect(() => {
    if (!token) {
      setRun(null);
      setWorkspace(null);
      setEvents([]);
      setLoadingRun(false);
      return;
    }

    let cancelled = false;
    setLoadingRun(true);

    async function load() {
      try {
        await loadRunData();
        if (!cancelled) {
          setErrorMessage(null);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(
            error instanceof Error
              ? error.message
              : t(locale, { ru: "Не удалось загрузить run.", en: "Failed to load run." })
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingRun(false);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [loadRunData, locale, token]);

  useEffect(() => {
    if (!token || !run || terminalStatuses.has(run.status)) {
      return;
    }

    const timer = setInterval(() => {
      void loadRunData().catch(() => undefined);
    }, 2000);

    return () => {
      clearInterval(timer);
    };
  }, [loadRunData, run, token]);

  const canCancel = useMemo(() => {
    if (!run) {
      return false;
    }
    return run.status === "running" || run.status === "starting_codex";
  }, [run]);
  const displaySummary = useMemo(() => {
    const normalized = tryExtractNestedMessage(run?.summary ?? null);
    if (!normalized) {
      return null;
    }
    if (normalized.startsWith("{\"type\":") || normalized.startsWith('{"type":')) {
      return null;
    }
    return normalized;
  }, [run?.summary]);
  const displayError = useMemo(
    () => tryExtractNestedMessage(run?.error_message ?? null),
    [run?.error_message]
  );
  const filteredChangedFiles = useMemo(() => {
    if (!workspace || !run) {
      return [];
    }
    if (terminalStatuses.has(run.status)) {
      return workspace.changed_files;
    }
    return workspace.changed_files.filter((path) => !isTemporaryExecutionPath(path));
  }, [run, workspace]);
  const hiddenTemporaryFilesCount = useMemo(() => {
    if (!workspace || !run || terminalStatuses.has(run.status)) {
      return 0;
    }
    return workspace.changed_files.filter((path) => isTemporaryExecutionPath(path)).length;
  }, [run, workspace]);

  async function onCancel() {
    if (!token || !run) {
      router.push("/auth/login");
      return;
    }

    setCancelling(true);
    setErrorMessage(null);
    try {
      const nextRun = await cancelRun(run.id, token);
      setRun(nextRun);
      const refreshedEvents = await fetchRunEvents(run.id, token);
      setEvents(refreshedEvents.items);
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : t(locale, { ru: "Не удалось отменить run.", en: "Failed to cancel run." })
      );
    } finally {
      setCancelling(false);
    }
  }

  async function onRefresh() {
    try {
      setErrorMessage(null);
      await loadRunData();
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : t(locale, { ru: "Не удалось обновить run.", en: "Failed to refresh run." })
      );
    }
  }

  if (loadingUser || loadingRun) {
    return (
      <div className="rounded-3xl border border-slate-200 bg-white px-5 py-4 text-sm text-slate-600 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:text-slate-300 dark:shadow-black/20">
        {loadingUser ? formatAuthLoading(locale) : t(locale, { ru: "Загружаем run...", en: "Loading run..." })}
      </div>
    );
  }

  if (!user) {
    return (
      <div className="rounded-3xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200">
        {t(locale, {
          ru: "Для просмотра run нужно авторизоваться в платформе.",
          en: "You need to sign in to view run details."
        })}
      </div>
    );
  }

  if (errorMessage || !run) {
    return (
      <div className="rounded-3xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-200">
        {errorMessage ?? t(locale, { ru: "Run не найден.", en: "Run not found." })}
      </div>
    );
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <RunStatusBadge locale={locale} status={run.status} />
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700 dark:bg-zinc-900/70 dark:text-slate-300">
              {run.team_title}
            </span>
            <span className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400 dark:text-slate-500">
              {run.repo_full_name}
            </span>
          </div>
          <div>
            <h1 className="text-3xl font-black text-slate-900 dark:text-slate-50">{run.title}</h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-600 dark:text-slate-300">
              {displaySummary ??
                t(locale, {
                  ru: "Summary для run не был задан явно; детали смотри в TASK.md и terminal output.",
                  en: "The run summary was not provided explicitly; see TASK.md and the terminal output for details."
                })}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={() => void onRefresh()} type="button" variant="secondary">
            <RefreshCcw className="mr-2 h-4 w-4" />
            {t(locale, { ru: "Обновить", en: "Refresh" })}
          </Button>
          {canCancel ? (
            <Button disabled={cancelling} onClick={() => void onCancel()} type="button" variant="ghost">
              {cancelling ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Square className="mr-2 h-4 w-4" />
              )}
              {t(locale, { ru: "Остановить run", en: "Stop run" })}
            </Button>
          ) : null}
        </div>
      </div>

      {displayError ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-200">
          {displayError}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
          <h2 className="mb-4 text-xl font-black text-slate-900 dark:text-slate-50">
            {t(locale, { ru: "Контекст запуска", en: "Run context" })}
          </h2>
          <div className="grid gap-4 text-sm text-slate-600 dark:text-slate-300 md:grid-cols-2">
            <p>
              <span className="font-semibold text-slate-900 dark:text-slate-100">ID:</span> {run.id}
            </p>
            <p>
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Runtime:", en: "Runtime:" })}
              </span>{" "}
              {run.runtime_target}
            </p>
            <p>
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Базовая ветка:", en: "Base branch:" })}
              </span>{" "}
              {run.base_branch}
            </p>
            <p>
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Рабочая ветка:", en: "Working branch:" })}
              </span>{" "}
              {run.working_branch ?? "-"}
            </p>
            <p>
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Workspace ID:", en: "Workspace ID:" })}
              </span>{" "}
              {run.workspace_id ?? "-"}
            </p>
            <p>
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Создан:", en: "Created:" })}
              </span>{" "}
              {formatTimestamp(locale, run.created_at)}
            </p>
            <div className="md:col-span-2">
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Путь workspace:", en: "Workspace path:" })}
              </span>{" "}
              <code className="break-all text-xs">{run.workspace_path ?? "-"}</code>
            </div>
            <div className="md:col-span-2">
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Путь репозитория:", en: "Repository path:" })}
              </span>{" "}
              <code className="break-all text-xs">{run.repo_path ?? "-"}</code>
            </div>
            {run.issue_number ? (
              <div className="md:col-span-2">
                <span className="font-semibold text-slate-900 dark:text-slate-100">
                  {t(locale, { ru: "Issue:", en: "Issue:" })}
                </span>{" "}
                <Link
                  className="font-semibold text-brand-700 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200"
                  href={`/repos/${encodeURIComponent(run.repo_owner)}/${encodeURIComponent(run.repo_name)}/issues/${run.issue_number}`}
                >
                  #{run.issue_number} {run.issue_title ?? ""}
                </Link>
              </div>
            ) : null}
            {run.pr_url ? (
              <div className="md:col-span-2">
                <a
                  className="inline-flex items-center gap-2 font-semibold text-brand-700 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200"
                  href={run.pr_url}
                  rel="noreferrer"
                  target="_blank"
                >
                  <ExternalLink className="h-4 w-4" />
                  {t(locale, { ru: "Открыть draft PR", en: "Open draft PR" })}
                </a>
              </div>
            ) : null}
          </div>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
          <h2 className="mb-4 text-xl font-black text-slate-900 dark:text-slate-50">
            {t(locale, { ru: "События run", en: "Run events" })}
          </h2>
          {events.length === 0 ? (
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "События пока не записаны.", en: "No run events have been recorded yet." })}
            </p>
          ) : (
            <ol className="space-y-3">
              {events.map((event) => (
                <li
                  className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 dark:border-zinc-800 dark:bg-zinc-900/70"
                  key={event.id}
                >
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <span className="rounded-full bg-slate-200 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-700 dark:bg-zinc-800 dark:text-slate-300">
                      {event.event_type}
                    </span>
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                      {formatTimestamp(locale, event.created_at)}
                    </span>
                  </div>
                  <p className="text-sm text-slate-700 dark:text-slate-200">
                    {extractEventMessage(event, locale)}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>

      {workspace ? (
        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
          <h2 className="mb-4 text-xl font-black text-slate-900 dark:text-slate-50">
            {t(locale, { ru: "SCM результат", en: "SCM result" })}
          </h2>
          <div className="grid gap-4 text-sm text-slate-600 dark:text-slate-300 md:grid-cols-2">
            <p>
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Статус workspace:", en: "Workspace status:" })}
              </span>{" "}
              {workspace.status}
            </p>
            <p>
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Текущая ветка:", en: "Current branch:" })}
              </span>{" "}
              {workspace.current_branch ?? "-"}
            </p>
            <p>
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Последний commit:", en: "Last commit:" })}
              </span>{" "}
              <code className="text-xs">{formatShortSha(workspace.last_commit_sha)}</code>
            </p>
            <p>
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Commit time:", en: "Commit time:" })}
              </span>{" "}
              {formatTimestamp(locale, workspace.committed_at)}
            </p>
            <p>
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Push time:", en: "Push time:" })}
              </span>{" "}
              {formatTimestamp(locale, workspace.pushed_at)}
            </p>
            <p>
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Pull request:", en: "Pull request:" })}
              </span>{" "}
              {workspace.pull_request_number ? `#${workspace.pull_request_number}` : "-"}
            </p>
            {workspace.last_commit_message ? (
              <div className="md:col-span-2">
                <span className="font-semibold text-slate-900 dark:text-slate-100">
                  {t(locale, { ru: "Commit message:", en: "Commit message:" })}
                </span>{" "}
                <span>{workspace.last_commit_message}</span>
              </div>
            ) : null}
            {workspace.pull_request_url ? (
              <div className="md:col-span-2">
                <a
                  className="inline-flex items-center gap-2 font-semibold text-brand-700 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200"
                  href={workspace.pull_request_url}
                  rel="noreferrer"
                  target="_blank"
                >
                  <ExternalLink className="h-4 w-4" />
                  {t(locale, { ru: "Открыть draft PR", en: "Open draft PR" })}
                </a>
              </div>
            ) : null}
            <div className="md:col-span-2">
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, {
                  ru: terminalStatuses.has(run.status)
                    ? "Tracked changes after run:"
                    : "Текущие tracked changes:",
                  en: terminalStatuses.has(run.status)
                    ? "Tracked changes after run:"
                    : "Current tracked changes:"
                })}
              </span>{" "}
              {filteredChangedFiles.length > 0 ? (
                <span>{filteredChangedFiles.join(", ")}</span>
              ) : (
                <span>
                  {workspace.has_changes && !terminalStatuses.has(run.status)
                    ? t(locale, {
                        ru: "пока виден только временный execution scaffolding",
                        en: "only temporary execution scaffolding is visible right now"
                      })
                    : t(locale, { ru: "рабочее дерево чистое", en: "worktree is clean" })}
                </span>
              )}
            </div>
            {hiddenTemporaryFilesCount > 0 ? (
              <div className="md:col-span-2 text-xs text-slate-500 dark:text-slate-400">
                {t(locale, {
                  ru: `Временные execution-файлы скрыты из этого блока до завершения run: ${hiddenTemporaryFilesCount}.`,
                  en: `Temporary execution files are hidden from this block until the run finishes: ${hiddenTemporaryFilesCount}.`
                })}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      <RunTerminalPanel locale={locale} runId={run.id} runStatus={run.status} token={token!} />
    </section>
  );
}
