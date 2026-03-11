import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { ExecutionPageContainer } from "@/components/layout/execution-page-container";
import { RunDetailsPanel } from "@/components/runs/run-details-panel";
import { t } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n.server";

export default function RunDetailsPage({ params }: { params: { id: string } }) {
  const locale = getRequestLocale();

  return (
    <ExecutionPageContainer>
      <section className="mx-auto w-full max-w-6xl space-y-6">
        <Link
          className="mb-4 inline-flex items-center gap-2 text-sm font-semibold text-brand-700 hover:text-brand-900 dark:text-slate-200 dark:hover:text-white"
          href="/runs"
        >
          <ArrowLeft className="h-4 w-4" />
          {t(locale, { ru: "Назад к запускам", en: "Back to runs" })}
        </Link>

        <RunDetailsPanel locale={locale} runId={params.id} />
      </section>
    </ExecutionPageContainer>
  );
}
