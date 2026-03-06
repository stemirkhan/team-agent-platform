import Link from "next/link";
import { PlusCircle, Sparkles, UsersRound } from "lucide-react";

import { TeamCard } from "@/components/teams/team-card";
import { Button } from "@/components/ui/button";
import { fetchTeams } from "@/lib/api";

export default async function TeamsCatalogPage() {
  const data = await fetchTeams();

  return (
    <section>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="mb-2 inline-flex items-center gap-1 rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-brand-700 ring-1 ring-brand-200">
            <Sparkles className="h-3.5 w-3.5" />
            Team presets
          </p>
          <h1 className="mb-2 inline-flex items-center gap-2 text-3xl font-black text-slate-900">
            <UsersRound className="h-8 w-8 text-brand-700" />
            Team Catalog
          </h1>
          <p className="text-sm text-slate-600">Published teams assembled from marketplace agents.</p>
        </div>
        <Link href="/teams/new">
          <Button>
            <PlusCircle className="mr-2 h-4 w-4" />
            Create Team
          </Button>
        </Link>
      </div>

      {data.items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500">
          No published teams yet. Use `POST /api/v1/teams` and `POST /api/v1/teams/&lt;slug&gt;/publish`
          to add your first team.
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data.items.map((team) => (
            <TeamCard key={team.id} team={team} />
          ))}
        </div>
      )}
    </section>
  );
}
