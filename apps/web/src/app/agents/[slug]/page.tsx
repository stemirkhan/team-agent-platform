import Link from "next/link";
import { notFound } from "next/navigation";

import { AgentDetailShowcase } from "@/components/agents/agent-detail-showcase";
import { fetchAgent } from "@/lib/api";
import { t } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n.server";

export default async function AgentDetailsPage({ params }: { params: { slug: string } }) {
  const locale = getRequestLocale();

  try {
    const agent = await fetchAgent(params.slug);

    return (
      <section className="mx-auto w-full max-w-6xl space-y-6">
        <Link className="mb-4 inline-flex text-sm font-semibold text-brand-700 hover:text-brand-900 dark:text-slate-200 dark:hover:text-white" href="/agents">
          &larr; {t(locale, { ru: "Назад к каталогу", en: "Back to catalog" })}
        </Link>

        <AgentDetailShowcase agent={agent} locale={locale} />
      </section>
    );
  } catch {
    notFound();
  }
}
