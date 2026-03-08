import { type RunStatus } from "@/lib/api";
import { formatRunStatus, type Locale } from "@/lib/i18n";

type RunStatusBadgeProps = {
  status: RunStatus;
  locale: Locale;
};

const runStatusClasses: Record<RunStatus, string> = {
  queued:
    "bg-slate-100 text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-800 dark:text-slate-200 dark:ring-zinc-700",
  preparing:
    "bg-sky-100 text-sky-800 ring-1 ring-sky-200 dark:bg-sky-500/10 dark:text-sky-300 dark:ring-sky-500/30",
  cloning_repo:
    "bg-sky-100 text-sky-800 ring-1 ring-sky-200 dark:bg-sky-500/10 dark:text-sky-300 dark:ring-sky-500/30",
  materializing_team:
    "bg-violet-100 text-violet-800 ring-1 ring-violet-200 dark:bg-violet-500/10 dark:text-violet-300 dark:ring-violet-500/30",
  starting_codex:
    "bg-brand-100 text-brand-800 ring-1 ring-brand-200 dark:bg-brand-500/10 dark:text-brand-300 dark:ring-brand-500/30",
  running:
    "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/30",
  committing:
    "bg-amber-100 text-amber-800 ring-1 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/30",
  pushing:
    "bg-amber-100 text-amber-800 ring-1 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/30",
  creating_pr:
    "bg-amber-100 text-amber-800 ring-1 ring-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/30",
  completed:
    "bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-500/30",
  failed:
    "bg-rose-100 text-rose-800 ring-1 ring-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:ring-rose-500/30",
  cancelled:
    "bg-slate-100 text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-800 dark:text-slate-300 dark:ring-zinc-700"
};

export function RunStatusBadge({ status, locale }: RunStatusBadgeProps) {
  return (
    <span
      className={[
        "inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em]",
        runStatusClasses[status]
      ].join(" ")}
    >
      {formatRunStatus(locale, status)}
    </span>
  );
}
