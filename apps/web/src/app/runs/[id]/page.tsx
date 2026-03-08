import Link from "next/link";
import { ArrowLeft, PlaySquare } from "lucide-react";

import { RunDetailsPanel } from "@/components/runs/run-details-panel";
import { t } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n.server";

export default function RunDetailsPage({ params }: { params: { id: string } }) {
  const locale = getRequestLocale();

  return (
    <section className="space-y-6">
      <div className="space-y-3">
        <Link
          className="inline-flex items-center gap-2 text-sm font-semibold text-brand-700 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200"
          href="/runs"
        >
          <ArrowLeft className="h-4 w-4" />
          {t(locale, { ru: "Назад к запускам", en: "Back to runs" })}
        </Link>
        <h1 className="mb-2 flex items-center gap-3 text-3xl font-black text-slate-900 dark:text-slate-50">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-brand-100 text-brand-700 ring-1 ring-brand-200 dark:bg-zinc-800 dark:text-slate-200 dark:ring-zinc-700">
            <PlaySquare className="h-5 w-5" />
          </span>
          <span>{t(locale, { ru: "Детали запуска", en: "Run details" })}</span>
        </h1>
      </div>

      <RunDetailsPanel locale={locale} runId={params.id} />
    </section>
  );
}
