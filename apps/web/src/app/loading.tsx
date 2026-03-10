import { Loader2 } from "lucide-react";

import { t } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n.server";

export default function Loading() {
  const locale = getRequestLocale();

  return (
    <section className="grid min-h-[48vh] place-items-center py-10">
      <div className="flex flex-col items-center gap-4 rounded-3xl border border-slate-200 bg-white/90 px-8 py-8 text-center shadow-sm dark:border-zinc-800 dark:bg-zinc-950/90">
        <Loader2 className="h-8 w-8 animate-spin text-slate-500 dark:text-slate-300" />
        <div className="space-y-1">
          <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            {t(locale, { ru: "Загружаю страницу...", en: "Loading page..." })}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {t(locale, {
              ru: "Подготавливаю интерфейс.",
              en: "Preparing the interface."
            })}
          </p>
        </div>
      </div>
    </section>
  );
}
