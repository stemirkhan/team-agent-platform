import Link from "next/link";

import type { Team } from "@/lib/api";

export function TeamCard({ team }: { team: Team }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">team</span>
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{team.status}</span>
      </div>

      <h2 className="mb-2 text-lg font-bold text-slate-900">{team.title}</h2>
      <p className="mb-5 line-clamp-3 text-sm text-slate-600">{team.description ?? "No description yet."}</p>

      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-500">by {team.author_name}</span>
        <Link className="font-semibold text-brand-700 hover:text-brand-900" href={`/teams/${team.slug}`}>
          Open
        </Link>
      </div>
    </article>
  );
}
