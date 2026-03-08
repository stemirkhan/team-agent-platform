import { PlaySquare } from "lucide-react";

import { RunsListPanel } from "@/components/runs/runs-list-panel";
import { t } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n.server";

export default function RunsPage() {
  const locale = getRequestLocale();

  return (
    <section className="space-y-6">
      <div>
        <h1 className="mb-2 flex items-center gap-3 text-3xl font-black text-slate-900 dark:text-slate-50">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-brand-100 text-brand-700 ring-1 ring-brand-200 dark:bg-zinc-800 dark:text-slate-200 dark:ring-zinc-700">
            <PlaySquare className="h-5 w-5" />
          </span>
          <span>{t(locale, { ru: "Запуски", en: "Runs" })}</span>
        </h1>
        <p className="max-w-3xl text-sm text-slate-600 dark:text-slate-300">
          {t(locale, {
            ru: "Execution-first контур: история run-ов, переход к live terminal и контроль статусов перед commit/push/PR слоями.",
            en: "The execution-first surface: run history, entry points to the live terminal, and status control before the commit/push/PR layer."
          })}
        </p>
      </div>

      <RunsListPanel locale={locale} />
    </section>
  );
}
