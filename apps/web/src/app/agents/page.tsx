import Link from "next/link";
import { Bot, PlusCircle, Sparkles } from "lucide-react";

import { AgentCard } from "@/components/agents/agent-card";
import { Button } from "@/components/ui/button";
import { fetchAgents } from "@/lib/api";

export default async function AgentsCatalogPage() {
  const data = await fetchAgents();

  return (
    <section>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="mb-2 inline-flex items-center gap-1 rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-brand-700 ring-1 ring-brand-200">
            <Sparkles className="h-3.5 w-3.5" />
            Marketplace
          </p>
          <h1 className="mb-2 inline-flex items-center gap-2 text-3xl font-black text-slate-900">
            <Bot className="h-8 w-8 text-brand-700" />
            Agent Catalog
          </h1>
          <p className="text-sm text-slate-600">Published agents available in the marketplace MVP.</p>
        </div>
        <Link href="/agents/new">
          <Button>
            <PlusCircle className="mr-2 h-4 w-4" />
            Create Agent
          </Button>
        </Link>
      </div>

      {data.items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500">
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
