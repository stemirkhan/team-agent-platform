import Link from "next/link";
import { ArrowUpRight, Bot, CircleCheckBig, User } from "lucide-react";

import type { Agent } from "@/lib/api";

export function AgentCard({ agent }: { agent: Agent }) {
  return (
    <article className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-brand-100/70 dark:border-zinc-800 dark:bg-zinc-900/90 dark:hover:shadow-black/45">
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="inline-flex items-center gap-1 rounded-full bg-brand-100 px-2 py-1 text-xs font-semibold text-brand-700 dark:bg-zinc-800 dark:text-slate-200">
          <Bot className="h-3.5 w-3.5" />
          {agent.category ?? "general"}
        </span>
        <span className="inline-flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
          <CircleCheckBig className="h-3.5 w-3.5" />
          {agent.status}
        </span>
      </div>

      <h2 className="mb-2 text-lg font-bold text-slate-900 dark:text-slate-50">{agent.title}</h2>
      <p className="mb-5 line-clamp-3 text-sm text-slate-600 dark:text-slate-300">{agent.short_description}</p>

      <div className="flex items-center justify-between text-sm">
        <span className="inline-flex items-center gap-1 text-slate-500 dark:text-slate-400">
          <User className="h-3.5 w-3.5" />
          {agent.author_name}
        </span>
        <Link
          className="inline-flex items-center gap-1 font-semibold text-brand-700 transition group-hover:text-brand-900 dark:text-slate-100 dark:group-hover:text-white"
          href={`/agents/${agent.slug}`}
        >
          Open
          <ArrowUpRight className="h-4 w-4" />
        </Link>
      </div>
    </article>
  );
}
