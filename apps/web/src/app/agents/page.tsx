import Link from "next/link";
import { Bot, PlusCircle } from "lucide-react";

import { AgentCard } from "@/components/agents/agent-card";
import { Button } from "@/components/ui/button";
import { fetchAgents } from "@/lib/api";
import { t } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n.server";

export default async function AgentsCatalogPage() {
  const locale = getRequestLocale();
  const data = await fetchAgents({ limit: 100, status: "published" });

  return (
    <section>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="mb-2 flex items-center gap-3 text-3xl font-black text-slate-900 dark:text-slate-50">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-brand-100 text-brand-700 ring-1 ring-brand-200 dark:bg-zinc-800 dark:text-slate-200 dark:ring-zinc-700">
              <Bot className="h-5 w-5" />
            </span>
            <span>{t(locale, { ru: "Каталог агентов", en: "Agent Catalog" })}</span>
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-300">
            {t(locale, {
              ru: "Опубликованные профили агентов для локального runtime workflow.",
              en: "Published agent profiles for the local runtime workflow."
            })}
          </p>
        </div>
        <Link href="/agents/new">
          <Button>
            <PlusCircle className="mr-2 h-4 w-4" />
            {t(locale, { ru: "Создать агента", en: "Create Agent" })}
          </Button>
        </Link>
      </div>

      {data.items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 dark:border-zinc-600 bg-white dark:bg-zinc-900 p-6 text-sm text-slate-500 dark:text-slate-400">
          {t(locale, {
            ru: "Пока нет опубликованных агентов. Создай первый профиль и опубликуй его, чтобы он появился в каталоге.",
            en: "No published agents yet. Create and publish the first profile to make it appear in the catalog."
          })}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.items.map((agent) => (
            <AgentCard agent={agent} key={agent.id} locale={locale} />
          ))}
        </div>
      )}
    </section>
  );
}
