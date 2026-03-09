import { Activity } from "lucide-react";

import { HostDiagnosticsPanel } from "@/components/diagnostics/host-diagnostics-panel";
import { ExecutionPageContainer } from "@/components/layout/execution-page-container";
import { fetchHostReadiness } from "@/lib/api";
import { t } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n.server";

export default async function DiagnosticsPage() {
  const locale = getRequestLocale();
  let initialSnapshot = null;
  let initialError: string | null = null;

  try {
    initialSnapshot = await fetchHostReadiness();
  } catch (error) {
    initialError =
      error instanceof Error
        ? error.message
        : t(locale, {
            ru: "Не удалось получить снимок диагностики.",
            en: "Failed to load diagnostics snapshot."
          });
  }

  return (
    <ExecutionPageContainer>
      <div>
        <h1 className="mb-2 flex items-center gap-3 text-3xl font-black text-slate-900 dark:text-slate-50">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-brand-100 text-brand-700 ring-1 ring-brand-200 dark:bg-zinc-800 dark:text-slate-200 dark:ring-zinc-700">
            <Activity className="h-5 w-5" />
          </span>
          <span>{t(locale, { ru: "Диагностика", en: "Diagnostics" })}</span>
        </h1>
        <p className="max-w-3xl text-sm text-slate-600 dark:text-slate-300">
          {t(locale, {
            ru: "Execution-first экран: он показывает активный execution source и readiness host executor, если тот уже поднят на хосте.",
            en: "The execution-first screen: it shows the active execution source and host executor readiness, if the host executor is already running."
          })}
        </p>
      </div>

      <HostDiagnosticsPanel
        initialError={initialError}
        initialSnapshot={initialSnapshot}
        locale={locale}
      />
    </ExecutionPageContainer>
  );
}
