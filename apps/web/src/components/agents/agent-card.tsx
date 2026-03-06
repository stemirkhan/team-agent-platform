import Link from "next/link";

import type { Agent } from "@/lib/api";

export function AgentCard({ agent }: { agent: Agent }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="rounded-full bg-brand-100 px-2 py-1 text-xs font-semibold text-brand-700">
          {agent.category ?? "general"}
        </span>
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{agent.status}</span>
      </div>

      <h2 className="mb-2 text-lg font-bold text-slate-900">{agent.title}</h2>
      <p className="mb-5 line-clamp-3 text-sm text-slate-600">{agent.short_description}</p>

      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-500">by {agent.author_name}</span>
        <Link className="font-semibold text-brand-700 hover:text-brand-900" href={`/agents/${agent.slug}`}>
          Open
        </Link>
      </div>
    </article>
  );
}
