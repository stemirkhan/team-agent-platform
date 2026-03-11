import { LayoutDashboard } from "lucide-react";

import { ExecutionPageContainer } from "@/components/layout/execution-page-container";
import { ExecutionBoardPanel } from "@/components/projects/execution-board-panel";
import { t } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n.server";

export default function ProjectsPage() {
  const locale = getRequestLocale();

  return (
    <ExecutionPageContainer>
      <div>
        <h1 className="mb-2 flex items-center gap-3 text-3xl font-black text-slate-900 dark:text-slate-50">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-brand-100 text-brand-700 ring-1 ring-brand-200 dark:bg-zinc-800 dark:text-slate-200 dark:ring-zinc-700">
            <LayoutDashboard className="h-5 w-5" />
          </span>
          <span>{t(locale, { ru: "Execution board", en: "Execution board" })}</span>
        </h1>
        <p className="max-w-3xl text-sm text-slate-600 dark:text-slate-300">
          {t(locale, {
            ru: "Канбан-представление для execution-first workflow: видно, что стоит в очереди, что уже выполняется, что финализируется и что упало.",
            en: "A kanban surface for the execution-first workflow: see what is queued, running, finalizing, completed, or failing."
          })}
        </p>
      </div>

      <ExecutionBoardPanel locale={locale} />
    </ExecutionPageContainer>
  );
}
