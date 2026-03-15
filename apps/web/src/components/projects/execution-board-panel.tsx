"use client";

import Link from "next/link";
import { ExternalLink, Loader2, Play, RefreshCcw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

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
  eyebrow: string;
  description: string;
  emptyLabel: string;
  statuses: RunStatus[];
  columnClassName: string;
  columnGlowClassName: string;
  headerBadgeClassName: string;
  countClassName: string;
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

const boardAutoScrollEdgePx = 96;
const boardAutoScrollMaxStep = 18;

function buildBoardColumns(locale: Locale): BoardColumn[] {
  return [
    {
      key: "queued",
      title: t(locale, { ru: "Очередь", en: "Queued" }),
      eyebrow: t(locale, { ru: "Intake", en: "Intake" }),
      description: t(locale, {
        ru: "Run создан и проходит подготовительные шаги.",
        en: "Runs that were created and are still moving through preparation."
      }),
      emptyLabel: t(locale, {
        ru: "Нет запусков в очереди.",
        en: "No queued runs."
      }),
      statuses: laneStatusMap.queued,
      columnClassName:
        "border-slate-200/80 bg-gradient-to-b from-white via-slate-50/90 to-slate-100/80 dark:border-zinc-800 dark:from-zinc-950 dark:via-zinc-950 dark:to-zinc-900/80",
      columnGlowClassName:
        "bg-[radial-gradient(circle_at_top,_rgba(148,163,184,0.18),_transparent_68%)] dark:bg-[radial-gradient(circle_at_top,_rgba(113,113,122,0.18),_transparent_70%)]",
      headerBadgeClassName:
        "border-slate-200 bg-white/85 text-slate-600 dark:border-zinc-700 dark:bg-zinc-950/85 dark:text-slate-300",
      countClassName:
        "bg-white/90 text-slate-700 ring-black/5 dark:bg-zinc-950/90 dark:text-slate-200 dark:ring-white/10"
    },
    {
      key: "active",
      title: t(locale, { ru: "В работе", en: "Active" }),
      eyebrow: t(locale, { ru: "Execute", en: "Execute" }),
      description: t(locale, {
        ru: "Runtime execution и связанные шаги orchestration идут прямо сейчас.",
        en: "Runtime execution and related orchestration steps are currently in progress."
      }),
      emptyLabel: t(locale, {
        ru: "Сейчас ничего не выполняется.",
        en: "Nothing is actively executing right now."
      }),
      statuses: laneStatusMap.active,
      columnClassName:
        "border-emerald-200/80 bg-gradient-to-b from-white via-emerald-50/90 to-emerald-100/70 dark:border-emerald-500/20 dark:from-zinc-950 dark:via-emerald-500/10 dark:to-zinc-900",
      columnGlowClassName:
        "bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.18),_transparent_66%)] dark:bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.22),_transparent_70%)]",
      headerBadgeClassName:
        "border-emerald-200/80 bg-white/85 text-emerald-700 dark:border-emerald-500/20 dark:bg-zinc-950/80 dark:text-emerald-300",
      countClassName:
        "bg-emerald-950/90 text-white ring-emerald-950/10 dark:bg-emerald-500/15 dark:text-emerald-200 dark:ring-emerald-500/10"
    },
    {
      key: "finalizing",
      title: t(locale, { ru: "Финализация", en: "Finalizing" }),
      eyebrow: t(locale, { ru: "Ship", en: "Ship" }),
      description: t(locale, {
        ru: "Run уже завершил runtime phase и оформляет git/PR слой.",
        en: "Runtime execution is done and the run is finishing the git and PR layer."
      }),
      emptyLabel: t(locale, {
        ru: "Нет запусков на финализации.",
        en: "No runs are in the finalization phase."
      }),
      statuses: laneStatusMap.finalizing,
      columnClassName:
        "border-amber-200/80 bg-gradient-to-b from-white via-amber-50/90 to-amber-100/70 dark:border-amber-500/20 dark:from-zinc-950 dark:via-amber-500/10 dark:to-zinc-900",
      columnGlowClassName:
        "bg-[radial-gradient(circle_at_top,_rgba(245,158,11,0.18),_transparent_68%)] dark:bg-[radial-gradient(circle_at_top,_rgba(245,158,11,0.2),_transparent_70%)]",
      headerBadgeClassName:
        "border-amber-200/80 bg-white/85 text-amber-700 dark:border-amber-500/20 dark:bg-zinc-950/80 dark:text-amber-300",
      countClassName:
        "bg-amber-950/90 text-white ring-amber-950/10 dark:bg-amber-500/15 dark:text-amber-200 dark:ring-amber-500/10"
    },
    {
      key: "completed",
      title: t(locale, { ru: "Готово", en: "Completed" }),
      eyebrow: t(locale, { ru: "Done", en: "Done" }),
      description: t(locale, {
        ru: "Успешно завершенные исполнения.",
        en: "Runs that completed successfully."
      }),
      emptyLabel: t(locale, {
        ru: "Успешных запусков пока нет.",
        en: "There are no completed runs yet."
      }),
      statuses: laneStatusMap.completed,
      columnClassName:
        "border-sky-200/80 bg-gradient-to-b from-white via-sky-50/90 to-sky-100/70 dark:border-sky-500/20 dark:from-zinc-950 dark:via-sky-500/10 dark:to-zinc-900",
      columnGlowClassName:
        "bg-[radial-gradient(circle_at_top,_rgba(14,165,233,0.18),_transparent_68%)] dark:bg-[radial-gradient(circle_at_top,_rgba(14,165,233,0.2),_transparent_70%)]",
      headerBadgeClassName:
        "border-sky-200/80 bg-white/85 text-sky-700 dark:border-sky-500/20 dark:bg-zinc-950/80 dark:text-sky-300",
      countClassName:
        "bg-sky-950/90 text-white ring-sky-950/10 dark:bg-sky-500/15 dark:text-sky-200 dark:ring-sky-500/10"
    },
    {
      key: "failed",
      title: t(locale, { ru: "Сбой", en: "Failed" }),
      eyebrow: t(locale, { ru: "Recover", en: "Recover" }),
      description: t(locale, {
        ru: "Прерванные, упавшие или отмененные запуски.",
        en: "Runs that were interrupted, failed, or cancelled."
      }),
      emptyLabel: t(locale, {
        ru: "Нет прерванных, упавших или отмененных запусков.",
        en: "No interrupted, failed, or cancelled runs."
      }),
      statuses: laneStatusMap.failed,
      columnClassName:
        "border-rose-200/80 bg-gradient-to-b from-white via-rose-50/90 to-rose-100/70 dark:border-rose-500/20 dark:from-zinc-950 dark:via-rose-500/10 dark:to-zinc-900",
      columnGlowClassName:
        "bg-[radial-gradient(circle_at_top,_rgba(244,63,94,0.18),_transparent_68%)] dark:bg-[radial-gradient(circle_at_top,_rgba(244,63,94,0.2),_transparent_70%)]",
      headerBadgeClassName:
        "border-rose-200/80 bg-white/85 text-rose-700 dark:border-rose-500/20 dark:bg-zinc-950/80 dark:text-rose-300",
      countClassName:
        "bg-rose-950/90 text-white ring-rose-950/10 dark:bg-rose-500/15 dark:text-rose-200 dark:ring-rose-500/10"
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

function formatRuntimeTarget(locale: Locale, runtimeTarget: Run["runtime_target"]) {
  if (runtimeTarget === "claude_code") {
    return t(locale, { ru: "Claude Code", en: "Claude Code" });
  }

  return t(locale, { ru: "Codex", en: "Codex" });
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
  const boardScrollerRef = useRef<HTMLDivElement | null>(null);
  const boardAutoScrollFrameRef = useRef<number | null>(null);
  const boardAutoScrollVelocityRef = useRef(0);

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

  function stopBoardAutoScroll() {
    boardAutoScrollVelocityRef.current = 0;

    if (boardAutoScrollFrameRef.current !== null) {
      cancelAnimationFrame(boardAutoScrollFrameRef.current);
      boardAutoScrollFrameRef.current = null;
    }
  }

  function startBoardAutoScroll() {
    if (boardAutoScrollFrameRef.current !== null) {
      return;
    }

    const tick = () => {
      const container = boardScrollerRef.current;
      if (!container) {
        boardAutoScrollFrameRef.current = null;
        return;
      }

      const velocity = boardAutoScrollVelocityRef.current;
      const maxScrollLeft = container.scrollWidth - container.clientWidth;

      if (velocity === 0 || maxScrollLeft <= 0) {
        boardAutoScrollFrameRef.current = null;
        return;
      }

      const nextScrollLeft = Math.max(0, Math.min(container.scrollLeft + velocity, maxScrollLeft));
      if (nextScrollLeft === container.scrollLeft) {
        stopBoardAutoScroll();
        return;
      }

      container.scrollLeft = nextScrollLeft;
      boardAutoScrollFrameRef.current = requestAnimationFrame(tick);
    };

    boardAutoScrollFrameRef.current = requestAnimationFrame(tick);
  }

  function updateBoardAutoScroll(clientX: number) {
    const container = boardScrollerRef.current;
    if (!container) {
      return;
    }

    const maxScrollLeft = container.scrollWidth - container.clientWidth;
    if (maxScrollLeft <= 0) {
      stopBoardAutoScroll();
      return;
    }

    const bounds = container.getBoundingClientRect();
    let velocity = 0;

    if (clientX <= bounds.left + boardAutoScrollEdgePx) {
      const ratio = 1 - (clientX - bounds.left) / boardAutoScrollEdgePx;
      velocity = -Math.max(0, Math.min(1, ratio)) * boardAutoScrollMaxStep;
      if (container.scrollLeft <= 0) {
        velocity = 0;
      }
    } else if (clientX >= bounds.right - boardAutoScrollEdgePx) {
      const ratio = 1 - (bounds.right - clientX) / boardAutoScrollEdgePx;
      velocity = Math.max(0, Math.min(1, ratio)) * boardAutoScrollMaxStep;
      if (container.scrollLeft >= maxScrollLeft) {
        velocity = 0;
      }
    }

    boardAutoScrollVelocityRef.current = velocity;

    if (velocity === 0) {
      stopBoardAutoScroll();
      return;
    }

    startBoardAutoScroll();
  }

  useEffect(() => {
    return () => {
      boardAutoScrollVelocityRef.current = 0;
      if (boardAutoScrollFrameRef.current !== null) {
        cancelAnimationFrame(boardAutoScrollFrameRef.current);
      }
    };
  }, []);

  return (
    <section className="relative overflow-hidden rounded-[2rem] border border-slate-200/80 bg-white/90 p-6 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950/95 dark:shadow-black/20">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-brand-100/60 via-slate-100/40 to-transparent dark:from-zinc-900 dark:via-zinc-950/40 dark:to-transparent" />
      <div className="pointer-events-none absolute -right-20 top-10 h-56 w-56 rounded-full bg-brand-200/20 blur-3xl dark:bg-slate-500/10" />
      <div className="relative space-y-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0 space-y-3">
            <div className="space-y-2">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400 dark:text-slate-500">
                {t(locale, { ru: "Live operating view", en: "Live operating view" })}
              </p>
              <div className="flex flex-col items-start gap-3 2xl:flex-row 2xl:items-center">
                <h2 className="text-2xl font-black tracking-tight text-slate-900 dark:text-slate-50 sm:text-[2rem]">
                  {t(locale, { ru: "Execution flow by lane", en: "Execution flow by lane" })}
                </h2>
                {user ? (
                  <div
                    aria-label={t(locale, { ru: "Метрики доски", en: "Board metrics" })}
                    className="flex max-w-full items-center divide-x divide-slate-200 overflow-hidden rounded-full border border-slate-200 bg-white/80 shadow-sm shadow-slate-200/60 backdrop-blur dark:divide-zinc-700 dark:border-zinc-700 dark:bg-zinc-950/80 dark:shadow-black/20"
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
              <p className="max-w-3xl text-sm leading-6 text-slate-600 dark:text-slate-300">
                {t(locale, {
                  ru: "Подготовка, активное исполнение, git/PR финализация и проблемные прогоны разделены на читаемые дорожки без изменения underlying run model.",
                  en: "Preparation, active execution, git or PR finalization, and problematic runs are separated into readable lanes without changing the underlying run model."
                })}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 xl:max-w-[28rem] xl:justify-end">
            {user ? (
              <select
                aria-label={t(locale, { ru: "Фильтр по репозиторию", en: "Repository filter" })}
                className="h-10 min-w-[15rem] rounded-full border border-slate-200 bg-white/90 px-4 py-1 text-sm font-medium text-slate-700 outline-none shadow-sm shadow-slate-200/60 backdrop-blur transition focus:border-brand-400 focus:ring-2 focus:ring-brand-100 dark:border-zinc-700 dark:bg-zinc-900/90 dark:text-slate-100 dark:shadow-black/20 dark:focus:border-brand-500 dark:focus:ring-brand-500/20"
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
              <Button className="h-10 rounded-full px-5">
                <Play className="mr-2 h-4 w-4" />
                {t(locale, { ru: "Новый запуск", en: "New run" })}
              </Button>
            </Link>
            <Button
              className="h-10 rounded-full px-4"
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
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white/60 px-4 py-5 text-sm text-slate-500 dark:border-zinc-700 dark:bg-zinc-950/40 dark:text-slate-400">
            {t(locale, {
              ru: "Под текущим фильтром карточек нет. Создай run или переключись на другой репозиторий.",
              en: "There are no cards for the current filter. Create a run or switch to another repository."
            })}
          </div>
        ) : null}

        {user && totalRuns > 0 ? (
          <div
            className="-mx-2 overflow-x-auto px-2 pb-3"
            onMouseLeave={stopBoardAutoScroll}
            onMouseMove={(event) => updateBoardAutoScroll(event.clientX)}
            ref={boardScrollerRef}
          >
            <div className="flex min-w-max items-start gap-4">
              {boardColumns.map((column) => (
                <section
                  className={cn(
                    "relative flex min-h-[20rem] w-[21rem] flex-none flex-col overflow-hidden rounded-[1.75rem] border p-4 shadow-sm shadow-slate-200/60 dark:shadow-black/20",
                    column.columnClassName
                  )}
                  key={column.key}
                >
                  <div
                    className={cn("pointer-events-none absolute inset-x-0 top-0 h-28", column.columnGlowClassName)}
                  />
                  <div className="relative mb-4">
                    <div className="flex items-center justify-between gap-2">
                      <div>
                        <p
                          className={cn(
                            "mb-2 inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.2em]",
                            column.headerBadgeClassName
                          )}
                        >
                          {column.eyebrow}
                        </p>
                        <h3 className="text-lg font-black text-slate-900 dark:text-slate-50">
                          {column.title}
                        </h3>
                      </div>
                      <span
                        className={cn(
                          "rounded-full px-2.5 py-1 text-xs font-semibold ring-1",
                          column.countClassName
                        )}
                      >
                        {groupedRuns[column.key].length}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{column.description}</p>
                  </div>

                  <div className="relative space-y-3">
                    {groupedRuns[column.key].length === 0 ? (
                      <div className="rounded-2xl border border-dashed border-slate-300/80 bg-white/70 px-4 py-4 text-sm text-slate-500 dark:border-zinc-700 dark:bg-zinc-950/50 dark:text-slate-400">
                        {column.emptyLabel}
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
          </div>
        ) : null}
      </div>
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
  const runtimeLabel = formatRuntimeTarget(locale, run.runtime_target);

  return (
    <article className="group min-w-0 rounded-[1.4rem] border border-white/80 bg-white/90 p-4 shadow-sm shadow-slate-200/70 transition duration-200 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950/90 dark:shadow-black/20 dark:hover:shadow-black/35">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-2">
          <RunStatusBadge locale={locale} status={run.status} />
          <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">
            <span>{runtimeLabel}</span>
            {run.working_branch ? (
              <span className="truncate normal-case tracking-normal text-slate-500 dark:text-slate-400">
                {run.working_branch}
              </span>
            ) : null}
          </div>
        </div>

        {run.pr_url ? (
          <a href={run.pr_url} rel="noreferrer" target="_blank">
            <Button className="h-9 w-9 shrink-0 rounded-full px-0" size="sm" type="button" variant="ghost">
              <ExternalLink className="h-4 w-4" />
            </Button>
          </a>
        ) : null}
      </div>

      <div className="mt-4 min-w-0 space-y-3">
        <h4 className="line-clamp-2 text-lg font-black leading-6 tracking-tight text-slate-900 dark:text-slate-50">
          {run.title}
        </h4>

        <div className="grid gap-2 text-sm text-slate-600 dark:text-slate-300">
          {showRepository ? (
            <div className="rounded-2xl border border-slate-200/80 bg-slate-50/80 px-3 py-2 dark:border-zinc-800 dark:bg-zinc-900/70">
              <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">
                {t(locale, { ru: "Repository", en: "Repository" })}
              </p>
              <p className="mt-1 truncate font-semibold text-slate-900 dark:text-slate-100">
                {run.repo_full_name}
              </p>
            </div>
          ) : null}
          <div className="rounded-2xl border border-slate-200/80 bg-slate-50/80 px-3 py-2 dark:border-zinc-800 dark:bg-zinc-900/70">
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">
              {t(locale, { ru: "Team", en: "Team" })}
            </p>
            <p className="mt-1 truncate font-semibold text-slate-900 dark:text-slate-100">
              {run.team_title}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
          {run.issue_number ? (
            <span className="rounded-full bg-slate-100 px-2.5 py-1 dark:bg-zinc-800">
              {t(locale, {
                ru: `Issue #${run.issue_number}`,
                en: `Issue #${run.issue_number}`
              })}
            </span>
          ) : null}
          {run.base_branch ? (
            <span className="rounded-full bg-slate-100 px-2.5 py-1 dark:bg-zinc-800">
              {t(locale, {
                ru: `Base ${run.base_branch}`,
                en: `Base ${run.base_branch}`
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
          <Button className="rounded-full" size="sm" variant="secondary">
            {t(locale, { ru: "Открыть", en: "Open" })}
          </Button>
        </Link>
      </div>
    </article>
  );
}
