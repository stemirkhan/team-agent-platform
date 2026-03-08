import Link from "next/link";
import { notFound } from "next/navigation";

import { AgentProfileForm } from "@/components/agents/agent-profile-form";
import { ExportControls } from "@/components/exports/export-controls";
import { fetchAgent } from "@/lib/api";
import { formatGeneralCategory, formatStatus, formatVerificationStatus, t } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n.server";

export default async function AgentDetailsPage({ params }: { params: { slug: string } }) {
  const locale = getRequestLocale();

  try {
    const agent = await fetchAgent(params.slug);

    return (
      <section className="w-full space-y-6">
        <Link className="mb-4 inline-flex text-sm font-semibold text-brand-700 hover:text-brand-900 dark:text-slate-200 dark:hover:text-white" href="/agents">
          &larr; {t(locale, { ru: "Назад к каталогу", en: "Back to catalog" })}
        </Link>

        <h1 className="mb-2 text-3xl font-black text-slate-900 dark:text-slate-50">{agent.title}</h1>
        <p className="mb-6 text-slate-600 dark:text-slate-300">{agent.short_description}</p>

        <div className="mb-6 grid gap-3 rounded-3xl border border-slate-200 bg-white p-6 text-sm text-slate-700 dark:border-zinc-800 dark:bg-zinc-950 dark:text-slate-200 md:grid-cols-2">
          <p>
            <span className="font-semibold">{t(locale, { ru: "Slug:", en: "Slug:" })}</span> {agent.slug}
          </p>
          <p>
            <span className="font-semibold">{t(locale, { ru: "Категория:", en: "Category:" })}</span> {agent.category ?? formatGeneralCategory(locale)}
          </p>
          <p>
            <span className="font-semibold">{t(locale, { ru: "Статус:", en: "Status:" })}</span> {formatStatus(locale, agent.status)}
          </p>
          <p>
            <span className="font-semibold">{t(locale, { ru: "Верификация:", en: "Verification:" })}</span> {formatVerificationStatus(locale, agent.verification_status)}
          </p>
          <p>
            <span className="font-semibold">{t(locale, { ru: "Автор:", en: "Author:" })}</span> {agent.author_name}
          </p>
        </div>

        <article className="prose-slate max-w-none rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
          <h2>{t(locale, { ru: "Полное описание", en: "Full Description" })}</h2>
          <p>{agent.full_description ?? t(locale, { ru: "Полное описание пока не добавлено.", en: "No full description yet." })}</p>
        </article>

        <AgentProfileForm agent={agent} locale={locale} />

        <ExportControls
          entityType="agent"
          locale={locale}
          slug={agent.slug}
          status={agent.status}
        />
      </section>
    );
  } catch {
    notFound();
  }
}
