"use client";

import { type ReactNode, useState } from "react";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  GitBranch,
  Github,
  RefreshCcw,
  ServerCog,
  Sparkles,
  TerminalSquare
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  refreshHostReadiness,
  type HostDiagnosticsSnapshot,
  type HostExecutionReadiness,
  type HostToolDiagnostics
} from "@/lib/api";
import { t, type Locale } from "@/lib/i18n";
import { LocalizedTimestamp } from "@/components/ui/localized-timestamp";

type HostDiagnosticsPanelProps = {
  locale: Locale;
  initialSnapshot: HostExecutionReadiness | null;
  initialError: string | null;
};

const statusBadgeClasses: Record<HostToolDiagnostics["status"], string> = {
  ready:
    "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/30",
  missing:
    "bg-rose-100 text-rose-800 ring-1 ring-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:ring-rose-500/30",
  outdated:
    "bg-amber-100 text-amber-800 ring-1 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/30",
  not_authenticated:
    "bg-amber-100 text-amber-800 ring-1 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/30",
  error:
    "bg-rose-100 text-rose-800 ring-1 ring-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:ring-rose-500/30"
};

function formatToolStatus(locale: Locale, status: HostToolDiagnostics["status"]): string {
  switch (status) {
    case "ready":
      return t(locale, { ru: "готов", en: "ready" });
    case "missing":
      return t(locale, { ru: "не найден", en: "missing" });
    case "outdated":
      return t(locale, { ru: "устарел", en: "outdated" });
    case "not_authenticated":
      return t(locale, { ru: "нет авторизации", en: "not authenticated" });
    case "error":
      return t(locale, { ru: "ошибка", en: "error" });
    default:
      return status;
  }
}

function getToolEntries(snapshot: HostDiagnosticsSnapshot) {
  return [
    {
      key: "git",
      icon: <GitBranch className="h-5 w-5" />,
      tool: snapshot.tools.git
    },
    {
      key: "gh",
      icon: <Github className="h-5 w-5" />,
      tool: snapshot.tools.gh
    },
    {
      key: "codex",
      icon: <Bot className="h-5 w-5" />,
      tool: snapshot.tools.codex
    },
    {
      key: "claude",
      icon: <Sparkles className="h-5 w-5" />,
      tool: snapshot.tools.claude
    },
    {
      key: "tmux",
      icon: <TerminalSquare className="h-5 w-5" />,
      tool: snapshot.tools.tmux
    }
  ];
}

function runtimeStatusBadge(
  locale: Locale,
  label: string,
  ready: boolean | undefined
): ReactNode {
  return (
    <span
      className={[
        "inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold",
        ready
          ? "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/30"
          : "bg-amber-100 text-amber-800 ring-1 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/30"
      ].join(" ")}
    >
      {ready ? <CheckCircle2 className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}
      {label}: {ready ? t(locale, { ru: "готов", en: "ready" }) : t(locale, { ru: "не готов", en: "not ready" })}
    </span>
  );
}

function ToolCard({
  locale,
  tool,
  icon
}: {
  locale: Locale;
  tool: HostToolDiagnostics;
  icon: ReactNode;
}) {
  return (
    <article className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className="mb-2 inline-flex h-10 w-10 items-center justify-center rounded-2xl bg-brand-100 text-brand-700 ring-1 ring-brand-200 dark:bg-zinc-800 dark:text-slate-200 dark:ring-zinc-700">
            {icon}
          </p>
          <h3 className="text-lg font-bold text-slate-900 dark:text-slate-50">{tool.name}</h3>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusBadgeClasses[tool.status]}`}>
          {formatToolStatus(locale, tool.status)}
        </span>
      </div>

      <div className="space-y-3 text-sm text-slate-600 dark:text-slate-300">
        <p>{tool.message}</p>
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 dark:border-zinc-800 dark:bg-zinc-900/70">
          <dl className="grid gap-2">
            <div className="grid gap-1">
              <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "Путь", en: "Path" })}
              </dt>
              <dd className="break-all text-slate-800 dark:text-slate-100">
                {tool.path ?? t(locale, { ru: "не найден", en: "not found" })}
              </dd>
            </div>
            <div className="grid gap-1">
              <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "Версия", en: "Version" })}
              </dt>
              <dd className="text-slate-800 dark:text-slate-100">
                {tool.version ?? t(locale, { ru: "не определена", en: "unavailable" })}
              </dd>
            </div>
            <div className="grid gap-1">
              <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "Минимум", en: "Minimum" })}
              </dt>
              <dd className="text-slate-800 dark:text-slate-100">{tool.minimum_version}</dd>
            </div>
            {tool.auth_required ? (
              <div className="grid gap-1">
                <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Авторизация", en: "Authentication" })}
                </dt>
                <dd className="text-slate-800 dark:text-slate-100">
                  {tool.auth_ok
                    ? t(locale, { ru: "активна", en: "active" })
                    : t(locale, { ru: "не активна", en: "not active" })}
                </dd>
              </div>
            ) : null}
          </dl>
        </div>

        {tool.remediation_steps.length > 0 ? (
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Что сделать", en: "Next steps" })}
            </p>
            <ul className="space-y-2">
              {tool.remediation_steps.map((step) => (
                <li
                  className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-zinc-800 dark:bg-zinc-900/70"
                  key={step}
                >
                  {step}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </article>
  );
}

function SnapshotOverview({
  locale,
  snapshot
}: {
  locale: Locale;
  snapshot: HostDiagnosticsSnapshot;
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/70">
        <h4 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          {t(locale, { ru: "Контекст процесса", en: "Process context" })}
        </h4>
        <dl className="grid gap-3 text-sm text-slate-700 dark:text-slate-200">
          <div className="grid gap-1">
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Пользователь", en: "User" })}
            </dt>
            <dd>{snapshot.executor_context.user}</dd>
          </div>
          <div className="grid gap-1">
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "HOME", en: "HOME" })}
            </dt>
            <dd className="break-all">{snapshot.executor_context.home}</dd>
          </div>
          <div className="grid gap-1">
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Текущий каталог", en: "Working directory" })}
            </dt>
            <dd className="break-all">{snapshot.executor_context.cwd}</dd>
          </div>
          <div className="grid gap-1">
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Окружение", en: "Runtime" })}
            </dt>
            <dd>
              {snapshot.executor_context.containerized
                ? t(locale, {
                    ru: `контейнер (${snapshot.executor_context.container_runtime ?? "unknown"})`,
                    en: `container (${snapshot.executor_context.container_runtime ?? "unknown"})`
                  })
                : t(locale, { ru: "host process", en: "host process" })}
            </dd>
          </div>
        </dl>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/70">
        <div className="mb-4 flex items-center gap-2 text-slate-900 dark:text-slate-50">
          <TerminalSquare className="h-5 w-5" />
          <h4 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {t(locale, { ru: "PTY и предупреждения", en: "PTY and warnings" })}
          </h4>
        </div>

        <div className="mb-4 flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
          {snapshot.pty_supported ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-300" />
          ) : (
            <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-300" />
          )}
          <span>
            {snapshot.pty_supported
              ? t(locale, { ru: "PTY доступен для live terminal.", en: "PTY is available for live terminal." })
              : t(locale, { ru: "PTY недоступен, live terminal не запустится.", en: "PTY is unavailable, so live terminal cannot start." })}
          </span>
        </div>

        <div className="mb-4 flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
          {snapshot.durable_transport_ready ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-300" />
          ) : (
            <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-300" />
          )}
          <span>
            {snapshot.durable_transport_ready
              ? t(locale, {
                  ru: "tmux доступен для durable transport и reattach.",
                  en: "tmux is available for durable transport and reattach."
                })
              : t(locale, {
                  ru: "tmux недоступен, поэтому live session recovery будет degraded.",
                  en: "tmux is unavailable, so live session recovery is degraded."
                })}
          </span>
        </div>

        {snapshot.warnings.length > 0 ? (
          <ul className="space-y-2 text-sm text-slate-700 dark:text-slate-200">
            {snapshot.warnings.map((warning) => (
              <li
                className="rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200"
                key={warning}
              >
                {warning}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-600 dark:text-slate-300">
            {t(locale, { ru: "Глобальных предупреждений нет.", en: "No global warnings." })}
          </p>
        )}
      </div>
    </div>
  );
}

function SnapshotSection({
  locale,
  title,
  subtitle,
  snapshot,
  tone
}: {
  locale: Locale;
  title: string;
  subtitle: string;
  snapshot: HostDiagnosticsSnapshot;
  tone: "primary" | "secondary";
}) {
  return (
    <section className="space-y-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="mb-3 flex items-center gap-2">
            <span
              className={[
                "rounded-full px-3 py-1 text-xs font-semibold",
                snapshot.ready
                  ? "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/30"
                  : tone === "primary"
                    ? "bg-amber-100 text-amber-800 ring-1 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/30"
                    : "bg-slate-100 text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-800 dark:text-slate-200 dark:ring-zinc-700"
              ].join(" ")}
            >
              {snapshot.ready
                ? t(locale, { ru: "готово к запуску", en: "ready to run" })
                : t(locale, { ru: "не готово", en: "not ready" })}
            </span>
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Обновлено:", en: "Updated:" })}{" "}
              <LocalizedTimestamp locale={locale} value={snapshot.generated_at} />
            </span>
          </div>
          <h2 className="text-2xl font-black text-slate-900 dark:text-slate-50">{title}</h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-600 dark:text-slate-300">{subtitle}</p>
        </div>
      </div>

      <SnapshotOverview locale={locale} snapshot={snapshot} />

      <div className="grid gap-4 xl:grid-cols-3">
        {getToolEntries(snapshot).map(({ key, icon, tool }) => (
          <ToolCard icon={icon} key={key} locale={locale} tool={tool} />
        ))}
      </div>
    </section>
  );
}

export function HostDiagnosticsPanel({
  locale,
  initialSnapshot,
  initialError
}: HostDiagnosticsPanelProps) {
  const [snapshot, setSnapshot] = useState(initialSnapshot);
  const [error, setError] = useState(initialError);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      const nextSnapshot = await refreshHostReadiness();
      setSnapshot(nextSnapshot);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : t(locale, {
              ru: "Не удалось обновить диагностику.",
              en: "Failed to refresh diagnostics."
            })
      );
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
        <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span
                className={[
                  "rounded-full px-3 py-1 text-xs font-semibold",
                  snapshot?.effective_ready
                    ? "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/30"
                    : "bg-amber-100 text-amber-800 ring-1 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/30"
                ].join(" ")}
              >
                {snapshot?.effective_ready
                  ? t(locale, { ru: "execution ready", en: "execution ready" })
                  : t(locale, { ru: "требуется внимание", en: "attention required" })}
              </span>
              {snapshot ? (
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Обновлено:", en: "Updated:" })}{" "}
                  <LocalizedTimestamp locale={locale} value={snapshot.generated_at} />
                </span>
              ) : null}
            </div>
            <h2 className="text-2xl font-black text-slate-900 dark:text-slate-50">
              {t(locale, { ru: "Сводка execution readiness", en: "Execution readiness summary" })}
            </h2>
            <p className="mt-2 max-w-3xl text-sm text-slate-600 dark:text-slate-300">
              {t(locale, {
                ru: "Здесь видно, готов ли текущий execution source к `git`, `gh` и runtime-specific workflow для Codex и Claude Code.",
                en: "This view shows whether the current execution source is ready for `git`, `gh`, and runtime-specific workflows for Codex and Claude Code."
              })}
            </p>
          </div>

          <Button onClick={handleRefresh} size="sm" variant="secondary">
            <RefreshCcw className={`mr-2 h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
            {isRefreshing
              ? t(locale, { ru: "Обновление...", en: "Refreshing..." })
              : t(locale, { ru: "Обновить", en: "Refresh" })}
          </Button>
        </div>

        {error ? (
          <div className="mb-5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300">
            {error}
          </div>
        ) : null}

        {snapshot ? (
          <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/70">
              <div className="mb-3 flex items-center gap-2">
                <ServerCog className="h-5 w-5 text-slate-700 dark:text-slate-200" />
                <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Активный execution source", en: "Active execution source" })}
                </h3>
              </div>
              <dl className="grid gap-3 text-sm text-slate-700 dark:text-slate-200">
                <div className="grid gap-1">
                  <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                    {t(locale, { ru: "Источник", en: "Source" })}
                  </dt>
                  <dd>{t(locale, { ru: "host executor", en: "host executor" })}</dd>
                </div>
                {snapshot.host_executor_url ? (
                  <div className="grid gap-1">
                    <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                      {t(locale, { ru: "Bridge URL", en: "Bridge URL" })}
                    </dt>
                    <dd className="break-all">{snapshot.host_executor_url}</dd>
                  </div>
                ) : null}
                <div className="grid gap-1">
                  <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                    {t(locale, { ru: "Связь с bridge", en: "Bridge reachability" })}
                  </dt>
                  <dd>
                    {snapshot.host_executor_reachable
                      ? t(locale, { ru: "доступен", en: "reachable" })
                      : t(locale, { ru: "недоступен", en: "unreachable" })}
                  </dd>
                </div>
              </dl>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/70">
              <div className="mb-3 flex items-center gap-2">
                {snapshot.effective_ready ? (
                  <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-300" />
                ) : (
                  <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-300" />
                )}
                <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Итог", en: "Outcome" })}
                </h3>
              </div>
              <p className="text-sm text-slate-700 dark:text-slate-200">
                {snapshot.effective_ready
                  ? t(locale, {
                      ru: "Текущий execution source готов к запуску GitHub/Codex workflow.",
                      en: "The current execution source is ready to run the GitHub/Codex workflow."
                    })
                  : t(locale, {
                      ru: "Текущий execution source еще не готов. Исправь проблемы ниже, прежде чем запускать run-сессии.",
                      en: "The current execution source is not ready yet. Fix the issues below before starting run sessions."
                    })}
              </p>
              {snapshot.host_executor_error ? (
                <p className="mt-3 rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-300">
                  {snapshot.host_executor_error}
                </p>
              ) : null}
              <div className="mt-4 flex flex-wrap gap-2">
                {runtimeStatusBadge(locale, "Codex", snapshot.runtime_ready.codex)}
                {runtimeStatusBadge(locale, "Claude Code", snapshot.runtime_ready.claude_code)}
              </div>
            </div>
          </div>
        ) : null}
      </div>

      {snapshot?.host_executor ? (
        <SnapshotSection
          locale={locale}
          snapshot={snapshot.host_executor}
          subtitle={t(locale, {
            ru: "Это целевой execution layer. Именно он должен видеть host `git`, `gh`, поддерживаемые runtime CLI и позже запускать реальные PTY-сессии.",
            en: "This is the target execution layer. It should be the process that sees host `git`, `gh`, the supported runtime CLIs, and later starts real PTY sessions."
          })}
          title={t(locale, { ru: "Host Executor", en: "Host Executor" })}
          tone="primary"
        />
      ) : snapshot ? (
        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="text-2xl font-black text-slate-900 dark:text-slate-50">
            {t(locale, { ru: "Host Executor", en: "Host Executor" })}
          </h2>
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
            {t(locale, {
              ru: "Платформа работает только через host executor и пока не может получить от него diagnostics snapshot.",
              en: "The platform now relies only on the host executor and cannot fetch its diagnostics snapshot yet."
            })}
          </p>
          <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200">
            {snapshot.host_executor_error ??
              t(locale, {
                ru: "Bridge пока не отвечает.",
                en: "The bridge is not responding yet."
              })}
          </div>
        </section>
      ) : null}
    </div>
  );
}
