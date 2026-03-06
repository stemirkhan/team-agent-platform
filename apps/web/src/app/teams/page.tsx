import Link from "next/link";

import { TeamCard } from "@/components/teams/team-card";
import { Button } from "@/components/ui/button";
import { fetchTeams } from "@/lib/api";

export default async function TeamsCatalogPage() {
  const data = await fetchTeams();

  return (
    <section>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="mb-2 text-3xl font-black text-slate-900">Team Catalog</h1>
          <p className="text-sm text-slate-600">Published teams assembled from marketplace agents.</p>
        </div>
        <Link href="/teams/new">
          <Button>Create Team</Button>
        </Link>
      </div>

      {data.items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500">
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
