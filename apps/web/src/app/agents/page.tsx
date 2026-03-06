import Link from "next/link";

import { AgentCard } from "@/components/agents/agent-card";
import { Button } from "@/components/ui/button";
import { fetchAgents } from "@/lib/api";

export default async function AgentsCatalogPage() {
  const data = await fetchAgents();

  return (
    <section>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="mb-2 text-3xl font-black text-slate-900">Agent Catalog</h1>
          <p className="text-sm text-slate-600">Published agents available in the marketplace MVP.</p>
        </div>
        <Link href="/agents/new">
          <Button>Create Agent</Button>
        </Link>
      </div>

      {data.items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500">
          No published agents yet. Use `POST /api/v1/agents` and `POST /api/v1/agents/&lt;slug&gt;/publish`
          to add your first card.
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data.items.map((agent) => (
            <AgentCard agent={agent} key={agent.id} />
          ))}
        </div>
      )}
    </section>
  );
}
