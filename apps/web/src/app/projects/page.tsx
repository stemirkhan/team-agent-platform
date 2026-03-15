import { LayoutDashboard } from "lucide-react";

import { ExecutionPageContainer } from "@/components/layout/execution-page-container";
import { ExecutionBoardPanel } from "@/components/projects/execution-board-panel";
import { t } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n.server";

export default function ProjectsPage() {
  const locale = getRequestLocale();

  return (
    <ExecutionPageContainer>
      <section className="relative overflow-hidden rounded-[2rem] border border-slate-200/80 bg-gradient-to-br from-white via-slate-50 to-brand-50/70 px-6 py-7 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-gradient-to-br dark:from-zinc-950 dark:via-zinc-950 dark:to-zinc-900 dark:shadow-black/20">
        <div className="pointer-events-none absolute inset-y-0 right-0 w-1/2 bg-[radial-gradient(circle_at_top_right,_rgba(59,130,246,0.14),_transparent_58%)] dark:bg-[radial-gradient(circle_at_top_right,_rgba(148,163,184,0.14),_transparent_60%)]" />
        <div className="relative flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="mb-3 inline-flex items-center gap-2 rounded-full border border-brand-200/70 bg-white/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-brand-800 shadow-sm shadow-brand-100/70 dark:border-zinc-700 dark:bg-zinc-900/80 dark:text-slate-200 dark:shadow-black/20">
              {t(locale, { ru: "Execution-first overview", en: "Execution-first overview" })}
            </p>
            <h1 className="mb-3 flex items-center gap-3 text-3xl font-black tracking-tight text-slate-900 dark:text-slate-50 sm:text-4xl">
              <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-100 text-brand-700 ring-1 ring-brand-200 shadow-sm shadow-brand-100 dark:bg-zinc-800 dark:text-slate-200 dark:ring-zinc-700 dark:shadow-black/20">
                <LayoutDashboard className="h-5 w-5" />
              </span>
              <span>{t(locale, { ru: "Execution board", en: "Execution board" })}</span>
            </h1>
            <p className="max-w-2xl text-sm leading-6 text-slate-600 dark:text-slate-300">
              {t(locale, {
                ru: "Канбан-поверхность для execution-first workflow: очереди, активные исполнения, финализация и сбои читаются как единый поток работы.",
                en: "A kanban surface for the execution-first workflow where queued work, active execution, finalization, and failures read as one operating view."
              })}
            </p>
          </div>

          <div className="grid gap-3 text-sm text-slate-600 dark:text-slate-300 sm:grid-cols-3 lg:min-w-[28rem]">
            <div className="rounded-2xl border border-white/80 bg-white/75 p-4 shadow-sm shadow-slate-200/60 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/80 dark:shadow-black/20">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">
                {t(locale, { ru: "Board role", en: "Board role" })}
              </p>
              <p className="mt-2 font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Единая картина исполнения", en: "One view of execution" })}
              </p>
            </div>
            <div className="rounded-2xl border border-white/80 bg-white/75 p-4 shadow-sm shadow-slate-200/60 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/80 dark:shadow-black/20">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">
                {t(locale, { ru: "Primary scan", en: "Primary scan" })}
              </p>
              <p className="mt-2 font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Lane state и активные узкие места", en: "Lane state and active bottlenecks" })}
              </p>
            </div>
            <div className="rounded-2xl border border-white/80 bg-white/75 p-4 shadow-sm shadow-slate-200/60 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/80 dark:shadow-black/20">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400 dark:text-slate-500">
                {t(locale, { ru: "Interaction", en: "Interaction" })}
              </p>
              <p className="mt-2 font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Фильтр, обновление и быстрый переход в run", en: "Filter, refresh, and quick run access" })}
              </p>
            </div>
          </div>
        </div>
      </section>

      <ExecutionBoardPanel locale={locale} />
    </ExecutionPageContainer>
  );
}
