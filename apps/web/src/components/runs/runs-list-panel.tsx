"use client";

import Link from "next/link";
import { ExternalLink, Loader2, Play, RefreshCcw } from "lucide-react";
import { useEffect, useState } from "react";

import { RunStatusBadge } from "@/components/runs/run-status-badge";
import { Button } from "@/components/ui/button";
import {
  clearAccessToken,
  fetchCurrentUser,
  getAccessToken,
  type AuthUser
} from "@/lib/auth-client";
import { fetchRuns, type Run, type RunStatus } from "@/lib/api";
import { formatAuthLoading, t, type Locale } from "@/lib/i18n";

type RunsListPanelProps = {
  locale: Locale;
};

type RunsFilter = "all" | RunStatus;

function formatTimestamp(locale: Locale, value: string | null): string {
  if (!value) {
    return "-";
  }

  return new Date(value).toLocaleString(locale === "ru" ? "ru-RU" : "en-US", {
    dateStyle: "medium",
    timeStyle: "short"
  });
}

const runFilters: RunsFilter[] = [
  "all",
  "queued",
  "running",
  "completed",
  "failed",
  "cancelled"
];

function formatFilterLabel(locale: Locale, value: RunsFilter): string {
  switch (value) {
    case "all":
      return t(locale, { ru: "все", en: "all" });
    case "queued":
      return t(locale, { ru: "очередь", en: "queued" });
    case "running":
      return t(locale, { ru: "в работе", en: "running" });
    case "completed":
      return t(locale, { ru: "успех", en: "completed" });
    case "failed":
      return t(locale, { ru: "ошибки", en: "failed" });
    case "cancelled":
      return t(locale, { ru: "отменены", en: "cancelled" });
    default:
      return value;
  }
}

export function RunsListPanel({ locale }: RunsListPanelProps) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loadingUser, setLoadingUser] = useState(true);
  const [runs, setRuns] = useState<Run[]>([]);
  const [statusFilter, setStatusFilter] = useState<RunsFilter>("all");
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);

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

  useEffect(() => {
    if (!token) {
      setRuns([]);
      return;
    }

    const currentToken = token;
    let cancelled = false;
    setLoadingRuns(true);

    async function loadRuns() {
      try {
        const payload = await fetchRuns(currentToken, {
          limit: 100,
          status: statusFilter === "all" ? undefined : statusFilter
        });
        if (!cancelled) {
          setRuns(payload.items);
          setErrorMessage(null);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(
            error instanceof Error
              ? error.message
              : t(locale, { ru: "Не удалось загрузить запуски.", en: "Failed to load runs." })
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingRuns(false);
        }
      }
    }

    void loadRuns();

    return () => {
      cancelled = true;
    };
  }, [locale, refreshTick, statusFilter, token]);

  return (
    <section className="space-y-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-black text-slate-900 dark:text-slate-50">
            {t(locale, { ru: "История запусков", en: "Run history" })}
          </h2>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
            {t(locale, {
              ru: "Здесь видны все run-ы текущего пользователя: статус, репозиторий, ветки, ошибки и переход к live terminal.",
              en: "This page shows all runs for the current user: status, repository, branches, errors, and entry points to the live terminal."
            })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/runs/new">
            <Button>
              <Play className="mr-2 h-4 w-4" />
              {t(locale, { ru: "Новый запуск", en: "New run" })}
            </Button>
          </Link>
          <Button
            disabled={loadingRuns || !token}
            onClick={() => setRefreshTick((current) => current + 1)}
            type="button"
            variant="secondary"
          >
            <RefreshCcw className="mr-2 h-4 w-4" />
            {t(locale, { ru: "Обновить страницу", en: "Refresh page" })}
          </Button>
        </div>
      </div>

      {loadingUser ? (
        <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3 text-sm text-slate-500 dark:border-zinc-800 dark:bg-zinc-900/70 dark:text-slate-400">
          {formatAuthLoading(locale)}
        </div>
      ) : null}

      {!loadingUser && !user ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200">
          <p>
            {t(locale, {
              ru: "Список запусков доступен только после входа в платформу.",
              en: "Run history is available only after signing in to the platform."
            })}
          </p>
        </div>
      ) : null}

      {user ? (
        <div className="flex flex-wrap gap-2">
          {runFilters.map((filter) => {
            const active = filter === statusFilter;
            return (
              <button
                className={[
                  "rounded-full px-3 py-1.5 text-xs font-semibold transition",
                  active
                    ? "bg-brand-100 text-brand-800 ring-1 ring-brand-300 dark:bg-zinc-800 dark:text-slate-100 dark:ring-zinc-600"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-zinc-900/70 dark:text-slate-300 dark:hover:bg-zinc-800"
                ].join(" ")}
                key={filter}
                onClick={() => setStatusFilter(filter)}
                type="button"
              >
                {formatFilterLabel(locale, filter)}
              </button>
            );
          })}
        </div>
      ) : null}

      {errorMessage ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-200">
          {errorMessage}
        </div>
      ) : null}

      {loadingRuns ? (
        <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3 text-sm text-slate-600 dark:border-zinc-800 dark:bg-zinc-900/70 dark:text-slate-300">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t(locale, { ru: "Загружаем run-ы...", en: "Loading runs..." })}
        </div>
      ) : null}

      {!loadingRuns && user && runs.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 px-4 py-4 text-sm text-slate-500 dark:border-zinc-700 dark:text-slate-400">
          {t(locale, {
            ru: "Пока нет ни одного run. Создай первый запуск и затем открой live terminal из деталки run.",
            en: "There are no runs yet. Create your first run and then open the live terminal from the run details page."
          })}
        </div>
      ) : null}

      {runs.length > 0 ? (
        <div className="space-y-4">
          {runs.map((run) => (
            <article
              className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 dark:border-zinc-800 dark:bg-zinc-900/70"
              key={run.id}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <RunStatusBadge locale={locale} status={run.status} />
                    <span className="rounded-full bg-slate-200 px-3 py-1 text-xs font-semibold text-slate-700 dark:bg-zinc-800 dark:text-slate-300">
                      {run.team_title}
                    </span>
                    <span className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400 dark:text-slate-500">
                      {run.repo_full_name}
                    </span>
                  </div>
                  <div>
                    <h3 className="text-lg font-black text-slate-900 dark:text-slate-50">{run.title}</h3>
                    <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                      {run.summary ??
                        t(locale, {
                          ru: "Краткое summary пока не задано.",
                          en: "No short summary was provided yet."
                        })}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Link href={`/runs/${run.id}`}>
                    <Button size="sm" variant="secondary">
                      {t(locale, { ru: "Открыть run", en: "Open run" })}
                    </Button>
                  </Link>
                  {run.pr_url ? (
                    <a href={run.pr_url} rel="noreferrer" target="_blank">
                      <Button size="sm" variant="ghost">
                        <ExternalLink className="mr-2 h-4 w-4" />
                        PR
                      </Button>
                    </a>
                  ) : null}
                </div>
              </div>

              <div className="mt-4 grid gap-3 text-sm text-slate-600 dark:text-slate-300 md:grid-cols-2 xl:grid-cols-4">
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
                    {t(locale, { ru: "Создан:", en: "Created:" })}
                  </span>{" "}
                  {formatTimestamp(locale, run.created_at)}
                </p>
                <p>
                  <span className="font-semibold text-slate-900 dark:text-slate-100">
                    {t(locale, { ru: "Завершен:", en: "Finished:" })}
                  </span>{" "}
                  {formatTimestamp(locale, run.finished_at)}
                </p>
              </div>

              {run.error_message ? (
                <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-200">
                  {run.error_message}
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
