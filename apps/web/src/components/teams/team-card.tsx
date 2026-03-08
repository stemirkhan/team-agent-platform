import Link from "next/link";
import { ArrowUpRight, CircleCheckBig, User, UsersRound } from "lucide-react";

import type { Team } from "@/lib/api";
import { formatStatus, t, type Locale } from "@/lib/i18n";

export function TeamCard({ team, locale }: { team: Team; locale: Locale }) {
  return (
    <article className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-brand-100/70 dark:border-zinc-800 dark:bg-zinc-900/90 dark:hover:shadow-black/45">
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 dark:bg-zinc-800 px-2 py-1 text-xs font-semibold text-slate-700 dark:text-slate-200">
          <UsersRound className="h-3.5 w-3.5" />
          {t(locale, { ru: "команда", en: "team" })}
        </span>
        <span className="inline-flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
          <CircleCheckBig className="h-3.5 w-3.5" />
          {formatStatus(locale, team.status)}
        </span>
      </div>

      <h2 className="mb-2 text-lg font-bold text-slate-900 dark:text-slate-50">{team.title}</h2>
      <p className="mb-5 line-clamp-3 text-sm text-slate-600 dark:text-slate-300">
        {team.description ?? t(locale, { ru: "Пока без описания.", en: "No description yet." })}
      </p>

      <div className="flex items-center justify-between text-sm">
        <span className="inline-flex items-center gap-1 text-slate-500 dark:text-slate-400">
          <User className="h-3.5 w-3.5" />
          {team.author_name}
        </span>
        <Link
          className="inline-flex items-center gap-1 font-semibold text-brand-700 transition group-hover:text-brand-900 dark:text-slate-100 dark:group-hover:text-white"
          href={`/teams/${team.slug}`}
        >
          {t(locale, { ru: "Открыть", en: "Open" })}
          <ArrowUpRight className="h-4 w-4" />
        </Link>
      </div>
    </article>
  );
}
