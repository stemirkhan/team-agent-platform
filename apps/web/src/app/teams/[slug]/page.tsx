import Link from "next/link";
import { notFound } from "next/navigation";

import { TeamDetailShowcase } from "@/components/teams/team-detail-showcase";
import { fetchTeam } from "@/lib/api";
import { t } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n.server";

export default async function TeamDetailsPage({ params }: { params: { slug: string } }) {
  const locale = getRequestLocale();

  try {
    const team = await fetchTeam(params.slug);

    return (
      <section className="mx-auto w-full max-w-6xl space-y-6">
        <Link className="mb-4 inline-flex text-sm font-semibold text-brand-700 hover:text-brand-900 dark:text-slate-200 dark:hover:text-white" href="/teams">
          &larr; {t(locale, { ru: "Назад к командам", en: "Back to teams" })}
        </Link>

        <TeamDetailShowcase locale={locale} team={team} />
      </section>
    );
  } catch {
    notFound();
  }
}
