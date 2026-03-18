"use client";

import { CheckCircle2, CircleOff, Clock3, Loader2, OctagonAlert, Slash } from "lucide-react";

import { LocalizedTimestamp } from "@/components/ui/localized-timestamp";
import {
  type RunReport,
  type RunReportCommand,
  type RunReportPhase,
  type RunReportPhaseStatus,
  type RuntimeTarget
} from "@/lib/api";
import { t, type Locale } from "@/lib/i18n";

type RunReportPanelProps = {
  locale: Locale;
  report: RunReport | null;
  runtimeTarget: RuntimeTarget;
  loading?: boolean;
};

function phaseTitle(locale: Locale, key: RunReportPhase["key"], runtimeTarget: RuntimeTarget): string {
  switch (key) {
    case "preparation":
      return t(locale, { ru: "Подготовка", en: "Preparation" });
    case "runtime":
      return runtimeTarget === "claude_code"
        ? t(locale, { ru: "Claude Code", en: "Claude Code" })
        : t(locale, { ru: "Codex", en: "Codex" });
    case "git_pr":
      return t(locale, { ru: "Git / PR", en: "Git / PR" });
    default:
      return key;
  }
}

function phaseStatusLabel(locale: Locale, status: RunReportPhaseStatus): string {
  switch (status) {
    case "completed":
      return t(locale, { ru: "Завершено", en: "Completed" });
    case "running":
      return t(locale, { ru: "Выполняется", en: "Running" });
    case "resuming":
      return t(locale, { ru: "Возобновляется", en: "Resuming" });
    case "interrupted":
      return t(locale, { ru: "Прервано", en: "Interrupted" });
    case "failed":
      return t(locale, { ru: "Ошибка", en: "Failed" });
    case "cancelled":
      return t(locale, { ru: "Отменено", en: "Cancelled" });
    case "not_available":
      return t(locale, { ru: "Недоступно", en: "Not available" });
    case "not_started":
    default:
      return t(locale, { ru: "Не запускалось", en: "Not started" });
  }
}

function statusClasses(status: RunReportPhaseStatus): string {
  switch (status) {
    case "completed":
      return "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-200";
    case "running":
      return "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/60 dark:bg-sky-950/30 dark:text-sky-200";
    case "resuming":
      return "border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-900/60 dark:bg-sky-950/30 dark:text-sky-200";
    case "interrupted":
      return "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200";
    case "failed":
      return "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-200";
    case "cancelled":
      return "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200";
    case "not_available":
      return "border-slate-200 bg-slate-50 text-slate-600 dark:border-zinc-700 dark:bg-zinc-900/70 dark:text-slate-300";
    case "not_started":
    default:
      return "border-slate-200 bg-white text-slate-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-slate-300";
  }
}

function StatusIcon({ status }: { status: RunReportPhaseStatus }) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-4 w-4" />;
    case "running":
      return <Loader2 className="h-4 w-4 animate-spin" />;
    case "resuming":
      return <Loader2 className="h-4 w-4 animate-spin" />;
    case "interrupted":
      return <Clock3 className="h-4 w-4" />;
    case "failed":
      return <OctagonAlert className="h-4 w-4" />;
    case "cancelled":
      return <Slash className="h-4 w-4" />;
    case "not_available":
      return <CircleOff className="h-4 w-4" />;
    case "not_started":
    default:
      return <Clock3 className="h-4 w-4" />;
  }
}

function renderCommand(locale: Locale, command: RunReportCommand, index: number) {
  return (
    <li
      className="rounded-xl border border-slate-200 bg-slate-50/70 p-3 dark:border-zinc-800 dark:bg-zinc-900/70"
      key={`${command.command}-${index}`}
    >
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs">
        <code className="break-all text-slate-700 dark:text-slate-100">{command.command}</code>
        <span className={command.succeeded ? "text-emerald-600 dark:text-emerald-300" : "text-rose-600 dark:text-rose-300"}>
          exit {command.exit_code}
        </span>
      </div>
      <div className="mb-2 text-xs text-slate-500 dark:text-slate-400">
        <LocalizedTimestamp locale={locale} value={command.started_at} /> -{" "}
        <LocalizedTimestamp locale={locale} value={command.finished_at} />
      </div>
      {command.output ? (
        <pre className="max-h-48 overflow-auto rounded-lg border border-slate-200 bg-white p-2 text-xs text-slate-700 dark:border-zinc-700 dark:bg-zinc-950 dark:text-slate-200">
          {command.output}
        </pre>
      ) : null}
    </li>
  );
}

function renderGitMeta(locale: Locale, phase: RunReportPhase) {
  const workingBranch = typeof phase.meta.working_branch === "string" ? phase.meta.working_branch : null;
  const commitSha = typeof phase.meta.commit_sha === "string" ? phase.meta.commit_sha : null;
  const prUrl = typeof phase.meta.pr_url === "string" ? phase.meta.pr_url : null;

  return (
    <div className="mt-3 grid gap-2 text-xs text-slate-600 dark:text-slate-300 md:grid-cols-3">
      <p>
        <span className="font-semibold text-slate-900 dark:text-slate-100">
          {t(locale, { ru: "Рабочая ветка:", en: "Working branch:" })}
        </span>{" "}
        {workingBranch ?? "-"}
      </p>
      <p>
        <span className="font-semibold text-slate-900 dark:text-slate-100">Commit SHA:</span>{" "}
        <code>{commitSha ?? "-"}</code>
      </p>
      <p>
        <span className="font-semibold text-slate-900 dark:text-slate-100">PR URL:</span>{" "}
        {prUrl ? (
          <a className="text-brand-700 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200" href={prUrl} rel="noreferrer" target="_blank">
            {prUrl}
          </a>
        ) : (
          "-"
        )}
      </p>
    </div>
  );
}

export function RunReportPanel({ locale, report, runtimeTarget, loading = false }: RunReportPanelProps) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
      <h2 className="mb-4 text-xl font-black text-slate-900 dark:text-slate-50">
        {t(locale, { ru: "Отчет запуска", en: "Run report" })}
      </h2>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t(locale, { ru: "Собираем отчет по фазам...", en: "Building the phase report..." })}
        </div>
      ) : !report || report.phases.length === 0 ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {t(locale, {
            ru: "Структурированный отчет пока недоступен для этого запуска.",
            en: "Structured run report is not available for this run yet."
          })}
        </p>
      ) : (
        <ol className="space-y-3">
          {report.phases.map((phase) => (
            <li className={`rounded-2xl border p-4 ${statusClasses(phase.status)}`} key={phase.key}>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm font-bold">
                  <StatusIcon status={phase.status} />
                  <span>
                    {phase.order}. {phaseTitle(locale, phase.key, runtimeTarget)}
                  </span>
                </div>
                <span className="rounded-full border border-current/30 px-2 py-0.5 text-xs font-semibold uppercase tracking-wide">
                  {phaseStatusLabel(locale, phase.status)}
                </span>
              </div>

              <p className="text-sm">{phase.description ?? "-"}</p>
              <p className="mt-1 text-xs opacity-80">
                <LocalizedTimestamp locale={locale} value={phase.first_event_at} /> -{" "}
                <LocalizedTimestamp locale={locale} value={phase.last_event_at} />
              </p>

              {phase.commands.length > 0 ? (
                <ol className="mt-3 space-y-2">{phase.commands.map((command, idx) => renderCommand(locale, command, idx))}</ol>
              ) : null}

              {phase.key === "git_pr" ? renderGitMeta(locale, phase) : null}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
