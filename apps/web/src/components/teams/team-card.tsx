import Link from "next/link";
import { ArrowUpRight, CircleCheckBig, User, UsersRound } from "lucide-react";

import type { Team } from "@/lib/api";

export function TeamCard({ team }: { team: Team }) {
  return (
    <article className="group rounded-2xl border border-slate-200 bg-white/90 p-5 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-brand-100/70">
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
          <UsersRound className="h-3.5 w-3.5" />
          team
        </span>
        <span className="inline-flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-slate-500">
          <CircleCheckBig className="h-3.5 w-3.5" />
          {team.status}
        </span>
      </div>

      <h2 className="mb-2 text-lg font-bold text-slate-900">{team.title}</h2>
      <p className="mb-5 line-clamp-3 text-sm text-slate-600">{team.description ?? "No description yet."}</p>

      <div className="flex items-center justify-between text-sm">
        <span className="inline-flex items-center gap-1 text-slate-500">
          <User className="h-3.5 w-3.5" />
          {team.author_name}
        </span>
        <Link
          className="inline-flex items-center gap-1 font-semibold text-brand-700 transition group-hover:text-brand-900"
          href={`/teams/${team.slug}`}
        >
          Open
          <ArrowUpRight className="h-4 w-4" />
        </Link>
      </div>
    </article>
  );
}
