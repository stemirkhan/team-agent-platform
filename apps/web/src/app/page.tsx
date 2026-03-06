import Link from "next/link";
import { ArrowRight, HeartPulse } from "lucide-react";

import { Button } from "@/components/ui/button";
import { fetchHealth } from "@/lib/api";

export default async function HomePage() {
  let backendStatus = "unavailable";

  try {
    const health = await fetchHealth();
    backendStatus = health.status;
  } catch {
    backendStatus = "unavailable";
  }

  return (
    <section className="grid gap-8 md:grid-cols-2 md:items-center">
      <div>
        <p className="mb-4 inline-flex items-center gap-2 rounded-full bg-brand-100 px-3 py-1 text-xs font-bold uppercase tracking-wide text-brand-800">
          <HeartPulse className="h-4 w-4" />
          Foundation Ready
        </p>
        <h1 className="mb-4 text-4xl font-black leading-tight text-slate-900 md:text-5xl">
          Marketplace for Subagents and Agent Teams
        </h1>
        <p className="mb-6 max-w-lg text-slate-600">
          MVP foundation is live: FastAPI backend, Next.js frontend, PostgreSQL, Redis, and first catalog
          endpoints.
        </p>
        <div className="flex items-center gap-3">
          <Link href="/agents">
            <Button>
              Open Catalog <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
          <Link href="/teams">
            <Button variant="secondary">Open Teams</Button>
          </Link>
          <span className="text-sm text-slate-500">Backend health: {backendStatus}</span>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white/90 p-6 shadow-lg">
        <h2 className="mb-3 text-xl font-bold text-slate-900">What is already in this build</h2>
        <ul className="space-y-2 text-sm text-slate-600">
          <li>FastAPI API v1 routing with health checks</li>
          <li>JWT auth endpoints and frontend login/register UI</li>
          <li>SQLAlchemy model and Alembic migration for agents</li>
          <li>Public catalog endpoints for agents and teams</li>
          <li>Next.js App Router pages wired to backend API</li>
          <li>Docker Compose local stack for web, backend, Postgres and Redis</li>
        </ul>
      </div>
    </section>
  );
}
