import Link from "next/link";
import { notFound } from "next/navigation";
import { PlaySquare } from "lucide-react";

import { ExportControls } from "@/components/exports/export-controls";
import { TeamBuilderControls } from "@/components/teams/team-builder-controls";
import { Button } from "@/components/ui/button";
import { fetchTeam } from "@/lib/api";
import { formatStatus, t } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n.server";

export default async function TeamDetailsPage({ params }: { params: { slug: string } }) {
  const locale = getRequestLocale();

  try {
    const team = await fetchTeam(params.slug);

    return (
      <section className="w-full space-y-6">
        <Link className="mb-4 inline-flex text-sm font-semibold text-brand-700 hover:text-brand-900 dark:text-slate-200 dark:hover:text-white" href="/teams">
          &larr; {t(locale, { ru: "Назад к командам", en: "Back to teams" })}
        </Link>

        <h1 className="mb-2 text-3xl font-black text-slate-900 dark:text-slate-50">{team.title}</h1>
        <p className="mb-6 text-slate-600 dark:text-slate-300">
          {team.description ?? t(locale, { ru: "Описание пока не добавлено.", en: "No description yet." })}
        </p>
        <div className="mb-6">
          <Link href={`/runs/new?team=${encodeURIComponent(team.slug)}`}>
            <Button variant="secondary">
              <PlaySquare className="mr-2 h-4 w-4" />
              {t(locale, { ru: "Запустить эту команду", en: "Run this team" })}
            </Button>
          </Link>
        </div>

        <div className="mb-6 grid gap-3 rounded-3xl border border-slate-200 bg-white p-6 text-sm text-slate-700 dark:border-zinc-800 dark:bg-zinc-950 dark:text-slate-200 md:grid-cols-2">
          <p>
            <span className="font-semibold">{t(locale, { ru: "Slug:", en: "Slug:" })}</span> {team.slug}
          </p>
          <p>
            <span className="font-semibold">{t(locale, { ru: "Статус:", en: "Status:" })}</span> {formatStatus(locale, team.status)}
          </p>
          <p>
            <span className="font-semibold">{t(locale, { ru: "Автор:", en: "Author:" })}</span> {team.author_name}
          </p>
          <p>
            <span className="font-semibold">{t(locale, { ru: "Элементов:", en: "Items:" })}</span> {team.items.length}
          </p>
        </div>

        <ExportControls entityType="team" locale={locale} slug={team.slug} status={team.status} />
        <TeamBuilderControls locale={locale} team={team} />
      </section>
    );
  } catch {
    notFound();
  }
}
