"use client";

import Link from "next/link";
import { ExternalLink, Loader2, Play, RefreshCcw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { RunStatusBadge } from "@/components/runs/run-status-badge";
import { Button } from "@/components/ui/button";
import { LocalizedTimestamp } from "@/components/ui/localized-timestamp";
import {
  clearAccessToken,
  fetchCurrentUser,
  getAccessToken,
  type AuthUser
} from "@/lib/auth-client";
import { fetchRuns, type Run, type RunStatus } from "@/lib/api";
import { cn } from "@/lib/utils";
import { formatAuthLoading, t, type Locale } from "@/lib/i18n";

type ExecutionBoardPanelProps = {
  locale: Locale;
};

type RunsBoardLane = "queued" | "active" | "finalizing" | "completed" | "failed";

type BoardColumn = {
  key: RunsBoardLane;
  title: string;
  description: string;
  emptyLabel: string;
  statuses: RunStatus[];
  accentClassName: string;
  countClassName: string;
  emptyRuleClassName: string;
};

type BoardMetricPillProps = {
  label: string;
  value: number;
  tone?: "neutral" | "active" | "muted";
};

const laneStatusMap: Record<RunsBoardLane, RunStatus[]> = {
  queued: ["queued", "preparing", "cloning_repo", "materializing_team"],
  active: ["running_setup", "starting_runtime", "starting_codex", "resuming", "running", "running_checks"],
  finalizing: ["committing", "pushing", "creating_pr"],
  completed: ["completed"],
  failed: ["interrupted", "failed", "cancelled"]
};

function buildBoardColumns(locale: Locale): BoardColumn[] {
  return [
    {
      key: "queued",
      title: t(locale, { ru: "Очередь", en: "Queued" }),
      description: t(locale, {
        ru: "Run создан и проходит подготовительные шаги.",
        en: "Runs that were created and are still moving through preparation."
      }),
      emptyLabel: t(locale, {
        ru: "Нет запусков в очереди.",
        en: "Nothing waiting yet."
      }),
      statuses: laneStatusMap.queued,
      accentClassName: "border-t-slate-400 dark:border-t-slate-500",
      countClassName:
        "bg-slate-100 text-slate-600 dark:bg-zinc-800 dark:text-slate-300",
      emptyRuleClassName: "bg-slate-400"
    },
    {
      key: "active",
      title: t(locale, { ru: "В работе", en: "Active" }),
      description: t(locale, {
        ru: "Runtime execution и связанные шаги orchestration идут прямо сейчас.",
        en: "Runtime execution and related orchestration steps are currently in progress."
      }),
      emptyLabel: t(locale, {
        ru: "Сейчас ничего не выполняется.",
        en: "Nothing running right now."
      }),
      statuses: laneStatusMap.active,
      accentClassName: "border-t-emerald-500 dark:border-t-emerald-400",
      countClassName:
        "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300",
      emptyRuleClassName: "bg-emerald-500"
    },
    {
      key: "finalizing",
      title: t(locale, { ru: "Финализация", en: "Finalizing" }),
      description: t(locale, {
        ru: "Run уже завершил runtime phase и оформляет git/PR слой.",
        en: "Runtime execution is done and the run is finishing the git and PR layer."
      }),
      emptyLabel: t(locale, {
        ru: "Нет запусков на финализации.",
        en: "No runs wrapping up."
      }),
      statuses: laneStatusMap.finalizing,
      accentClassName: "border-t-amber-400 dark:border-t-amber-400",
      countClassName:
        "bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
      emptyRuleClassName: "bg-amber-400"
    },
    {
      key: "completed",
      title: t(locale, { ru: "Готово", en: "Completed" }),
      description: t(locale, {
        ru: "Успешно завершенные исполнения.",
        en: "Runs that completed successfully."
      }),
      emptyLabel: t(locale, {
        ru: "Успешных запусков пока нет.",
        en: "No completed runs yet."
      }),
      statuses: laneStatusMap.completed,
      accentClassName: "border-t-sky-500 dark:border-t-sky-400",
      countClassName:
        "bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
      emptyRuleClassName: "bg-sky-500"
    },
    {
      key: "failed",
      title: t(locale, { ru: "Сбой", en: "Failed" }),
      description: t(locale, {
        ru: "Прерванные, упавшие или отмененные запуски.",
        en: "Runs that were interrupted, failed, or cancelled."
      }),
      emptyLabel: t(locale, {
        ru: "Нет прерванных, упавших или отмененных запусков.",
        en: "Clean — no failures."
      }),
      statuses: laneStatusMap.failed,
      accentClassName: "border-t-rose-500 dark:border-t-rose-400",
      countClassName:
        "bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300",
      emptyRuleClassName: "bg-rose-500"
    }
  ];
}

function resolveLane(status: RunStatus): RunsBoardLane {
  for (const [lane, statuses] of Object.entries(laneStatusMap) as [RunsBoardLane, RunStatus[]][]) {
    if (statuses.includes(status)) {
      return lane;
    }
  }

  return "queued";
}

function collectRepositoryOptions(runs: Run[]): string[] {
  return Array.from(new Set(runs.map((run) => run.repo_full_name))).sort((left, right) =>
    left.localeCompare(right)
  );
}

function BoardMetricPill({ label, value, tone = "neutral" }: BoardMetricPillProps) {
  const toneClassName =
    tone === "active"
      ? "text-emerald-700 dark:text-emerald-400"
      : "text-slate-700 dark:text-slate-200";

  return (
    <div className="flex flex-col items-center leading-none">
      <span className={cn("text-xl font-black tabular-nums", toneClassName)}>{value}</span>
      <span className="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-slate-500">
        {label}
      </span>
    </div>
  );
}

export function ExecutionBoardPanel({ locale }: ExecutionBoardPanelProps) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loadingUser, setLoadingUser] = useState(true);
  const [runs, setRuns] = useState<Run[]>([]);
  const [repositoryOptions, setRepositoryOptions] = useState<string[]>([]);
  const [selectedRepository, setSelectedRepository] = useState<string>("all");
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);

  const boardColumns = useMemo(() => buildBoardColumns(locale), [locale]);

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
      setRepositoryOptions([]);
      setSelectedRepository("all");
      return;
    }

    let cancelled = false;
    const currentToken = token;
    setLoadingRuns(true);

    async function loadRuns() {
      try {
        const payload = await fetchRuns(currentToken, {
          limit: 100,
          repo: selectedRepository === "all" ? undefined : selectedRepository
        });

        if (!cancelled) {
          setRuns(payload.items);
          setRepositoryOptions((current) => {
            if (selectedRepository === "all") {
              return collectRepositoryOptions(payload.items);
            }

            const next = new Set(current);
            next.add(selectedRepository);
            for (const repo of collectRepositoryOptions(payload.items)) {
              next.add(repo);
            }
            return Array.from(next).sort((left, right) => left.localeCompare(right));
          });
          setErrorMessage(null);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(
            error instanceof Error
              ? error.message
              : t(locale, {
                  ru: "Не удалось загрузить execution board.",
                  en: "Failed to load the execution board."
                })
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
  }, [locale, refreshTick, selectedRepository, token]);

  const groupedRuns = useMemo(() => {
    const initialState: Record<RunsBoardLane, Run[]> = {
      queued: [],
      active: [],
      finalizing: [],
      completed: [],
      failed: []
    };

    for (const run of runs) {
      initialState[resolveLane(run.status)].push(run);
    }

    return initialState;
  }, [runs]);

  const totalRuns = runs.length;

  return (
    <section className="space-y-5 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
      {/* ── Primary header ── */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-2xl font-black text-slate-900 dark:text-slate-50">
            {t(locale, { ru: "Execution board", en: "Execution board" })}
          </h2>
          {user ? (
            <div
              aria-label={t(locale, { ru: "Метрики доски", en: "Board metrics" })}
              className="flex items-center divide-x divide-slate-200 overflow-hidden rounded-full border border-slate-200 bg-slate-50 dark:divide-zinc-700 dark:border-zinc-700 dark:bg-zinc-900"
            >
              <div className="px-4 py-1.5">
                <BoardMetricPill
                  label={t(locale, { ru: "Карточек", en: "Cards" })}
                  value={totalRuns}
                />
              </div>
              <div className="px-4 py-1.5">
                <BoardMetricPill
                  label={t(locale, { ru: "Активных", en: "Active" })}
                  tone="active"
                  value={groupedRuns.active.length + groupedRuns.finalizing.length}
                />
              </div>
              <div className="px-4 py-1.5">
                <BoardMetricPill
                  label={t(locale, { ru: "Репозит.", en: "Repos" })}
                  value={selectedRepository === "all" ? repositoryOptions.length : 1}
                />
              </div>
            </div>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {user ? (
            <select
              aria-label={t(locale, { ru: "Фильтр по репозиторию", en: "Repository filter" })}
              className="h-9 rounded-full border border-slate-200 bg-white px-3 py-1 text-sm font-medium text-slate-700 outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-slate-100 dark:focus:border-brand-500 dark:focus:ring-brand-500/20"
              onChange={(event) => setSelectedRepository(event.target.value)}
              value={selectedRepository}
            >
              <option value="all">
                {t(locale, { ru: "Все репозитории", en: "All repositories" })}
              </option>
              {repositoryOptions.map((repo) => (
                <option key={repo} value={repo}>
                  {repo}
                </option>
              ))}
            </select>
          ) : null}
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
            {t(locale, { ru: "Обновить", en: "Refresh" })}
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
          {t(locale, {
            ru: "Execution board доступен только после входа в платформу.",
            en: "The execution board is available only after signing in to the platform."
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
          {t(locale, { ru: "Загружаем execution board...", en: "Loading the execution board..." })}
        </div>
      ) : null}

      {!loadingRuns && user && totalRuns === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 px-4 py-4 text-sm text-slate-500 dark:border-zinc-700 dark:text-slate-400">
          {t(locale, {
            ru: "Под текущим фильтром карточек нет. Создай run или переключись на другой репозиторий.",
            en: "There are no cards for the current filter. Create a run or switch to another repository."
          })}
        </div>
      ) : null}

      {user && totalRuns > 0 ? (
        <div className="grid gap-3 xl:grid-cols-5 xl:items-start">
          {boardColumns.map((column) => (
            <section
              className={cn(
                "flex min-h-[18rem] self-start flex-col rounded-2xl border border-t-2 border-slate-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950",
                column.accentClassName
              )}
              key={column.key}
            >
              {/* Lane header */}
              <div className="mb-3">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-bold tracking-wide text-slate-800 dark:text-slate-100">
                    {column.title}
                  </h3>
                  <span
                    className={cn(
                      "min-w-[1.5rem] rounded-full px-2 py-0.5 text-center text-xs font-semibold tabular-nums",
                      column.countClassName
                    )}
                  >
                    {groupedRuns[column.key].length}
                  </span>
                </div>
                <p className="mt-1.5 text-[11px] leading-snug text-slate-400 dark:text-slate-500">
                  {column.description}
                </p>
              </div>

              <div className="mb-3 border-t border-slate-100 dark:border-zinc-800" />

              <div className="space-y-3">
                {groupedRuns[column.key].length === 0 ? (
                  <div className="flex flex-col items-center gap-2 py-8 text-center">
                    <div
                      className={cn(
                        "h-0.5 w-8 rounded-full opacity-40",
                        column.emptyRuleClassName
                      )}
                    />
                    <p className="text-xs font-medium text-slate-400 dark:text-slate-500">
                      {column.emptyLabel}
                    </p>
                  </div>
                ) : null}

                {groupedRuns[column.key].map((run) => (
                  <ExecutionBoardCard
                    key={run.id}
                    locale={locale}
                    run={run}
                    showRepository={selectedRepository === "all"}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function ExecutionBoardCard({
  locale,
  run,
  showRepository
}: {
  locale: Locale;
  run: Run;
  showRepository: boolean;
}) {
  const showErrorMarker = Boolean(
    run.error_message &&
      (run.status === "interrupted" || run.status === "failed" || run.status === "cancelled")
  );
  const timestampLabel =
    run.finished_at &&
    (run.status === "completed" ||
      run.status === "interrupted" ||
      run.status === "failed" ||
      run.status === "cancelled")
      ? t(locale, { ru: "Завершен", en: "Finished" })
      : t(locale, { ru: "Создан", en: "Created" });
  const timestampValue =
    run.finished_at &&
    (run.status === "completed" ||
      run.status === "interrupted" ||
      run.status === "failed" ||
      run.status === "cancelled")
      ? run.finished_at
      : run.created_at;

  return (
    <article className="min-w-0 rounded-2xl border border-white/70 bg-white p-4 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <RunStatusBadge locale={locale} status={run.status} />
        </div>

        {run.pr_url ? (
          <a href={run.pr_url} rel="noreferrer" target="_blank">
            <Button className="h-9 w-9 shrink-0 px-0" size="sm" type="button" variant="ghost">
              <ExternalLink className="h-4 w-4" />
            </Button>
          </a>
        ) : null}
      </div>

      <div className="mt-3 min-w-0 space-y-2">
        <h4 className="line-clamp-2 text-lg font-black leading-6 text-slate-900 dark:text-slate-50">
          {run.title}
        </h4>

        {showRepository ? (
          <p className="truncate text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
            {run.repo_full_name}
          </p>
        ) : null}

        <p className="truncate text-sm font-medium text-slate-500 dark:text-slate-400">{run.team_title}</p>

        <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
          {run.issue_number ? (
            <span className="rounded-full bg-slate-100 px-2.5 py-1 dark:bg-zinc-800">
              {t(locale, {
                ru: `Issue #${run.issue_number}`,
                en: `Issue #${run.issue_number}`
              })}
            </span>
          ) : null}
          {showErrorMarker ? (
            <span className="rounded-full bg-rose-100 px-2.5 py-1 text-rose-700 dark:bg-rose-500/10 dark:text-rose-300">
              {t(locale, { ru: "Есть ошибка", en: "Has error" })}
            </span>
          ) : null}
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between gap-3 border-t border-slate-200 pt-3 dark:border-zinc-800">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
            {timestampLabel}
          </p>
          <LocalizedTimestamp
            className="mt-1 block text-sm font-medium text-slate-900 dark:text-slate-100"
            dateStyle="short"
            locale={locale}
            timeStyle={undefined}
            value={timestampValue}
          />
        </div>

        <Link href={`/runs/${run.id}`}>
          <Button size="sm" variant="secondary">
            {t(locale, { ru: "Открыть", en: "Open" })}
          </Button>
        </Link>
      </div>
    </article>
  );
}
