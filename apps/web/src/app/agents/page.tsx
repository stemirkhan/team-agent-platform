import Link from "next/link";
import { Bot, PlusCircle } from "lucide-react";

import { AgentCard } from "@/components/agents/agent-card";
import { Button } from "@/components/ui/button";
import { fetchAgents } from "@/lib/api";

export default async function AgentsCatalogPage() {
  const data = await fetchAgents();

  return (
    <section>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="mb-2 flex items-center gap-3 text-3xl font-black text-slate-900 dark:text-slate-50">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-brand-100 text-brand-700 ring-1 ring-brand-200 dark:bg-brand-900/40 dark:text-brand-300 dark:ring-brand-700/60">
              <Bot className="h-5 w-5" />
            </span>
            <span>Agent Catalog</span>
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-300">Published agents available in the marketplace MVP.</p>
        </div>
        <Link href="/agents/new">
          <Button>
            <PlusCircle className="mr-2 h-4 w-4" />
            Create Agent
          </Button>
        </Link>
      </div>

      {data.items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 p-6 text-sm text-slate-500 dark:text-slate-400">
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
