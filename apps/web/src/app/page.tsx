import Link from "next/link";
import { ArrowRight, Bot, Flame, ShieldCheck, Sparkles, UsersRound } from "lucide-react";

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
    <section className="space-y-8">
      <div className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
        <div>
          <h1 className="mb-4 text-4xl font-black leading-tight text-slate-900 dark:text-slate-50 md:text-5xl">
            Build Better Agent Workflows With Curated Teams
          </h1>
          <p className="mb-6 max-w-xl text-slate-600 dark:text-slate-300">
            Marketplace MVP is online: catalog, auth, team builder, reviews, and API-first backend wired to
            PostgreSQL and Redis.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Link href="/agents">
              <Button>
                Open Agents <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
            <Link href="/teams">
              <Button variant="secondary">
                Open Teams <UsersRound className="ml-2 h-4 w-4" />
              </Button>
            </Link>
            <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-600 ring-1 ring-slate-200 dark:bg-zinc-900 dark:text-slate-300 dark:ring-zinc-700">
              Backend health: {backendStatus}
            </span>
          </div>

          <div className="mt-6 flex flex-wrap gap-2 text-xs font-semibold">
            <span className="inline-flex items-center gap-1 rounded-full bg-white px-2.5 py-1 text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-900 dark:text-slate-200 dark:ring-zinc-700">
              <Bot className="h-3.5 w-3.5 text-brand-700 dark:text-slate-300" />
              Agents catalog
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-white px-2.5 py-1 text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-900 dark:text-slate-200 dark:ring-zinc-700">
              <UsersRound className="h-3.5 w-3.5 text-brand-700 dark:text-slate-300" />
              Team builder
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-white px-2.5 py-1 text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-900 dark:text-slate-200 dark:ring-zinc-700">
              <ShieldCheck className="h-3.5 w-3.5 text-teal-700 dark:text-slate-300" />
              Reviews & trust
            </span>
          </div>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-lg shadow-brand-100/70 dark:border-zinc-800 dark:bg-zinc-900/90 dark:shadow-black/45">
          <h2 className="mb-3 text-xl font-bold text-slate-900 dark:text-slate-50">What is already in this build</h2>
          <ul className="space-y-2 text-sm text-slate-600 dark:text-slate-300">
            <li className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-brand-700 dark:text-slate-300" />
              FastAPI API v1 routing with health checks
            </li>
            <li className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-brand-700 dark:text-slate-300" />
              JWT auth endpoints and frontend login/register UI
            </li>
            <li className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-brand-700 dark:text-slate-300" />
              SQLAlchemy model and Alembic migration for agents
            </li>
            <li className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-brand-700 dark:text-slate-300" />
              Public catalog endpoints for agents and teams
            </li>
            <li className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-brand-700 dark:text-slate-300" />
              Next.js App Router pages wired to backend API
            </li>
            <li className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-brand-700 dark:text-slate-300" />
              Docker Compose local stack for web, backend, Postgres and Redis
            </li>
          </ul>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/90">
          <p className="mb-2 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-brand-700 dark:text-slate-300">
            <Flame className="h-4 w-4" />
            Discover
          </p>
          <h3 className="mb-1 text-lg font-bold text-slate-900 dark:text-slate-50">Explore vetted agents</h3>
          <p className="text-sm text-slate-600 dark:text-slate-300">Browse by domain, status, and quality signals.</p>
        </article>
        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/90">
          <p className="mb-2 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-brand-700 dark:text-slate-300">
            <UsersRound className="h-4 w-4" />
            Compose
          </p>
          <h3 className="mb-1 text-lg font-bold text-slate-900 dark:text-slate-50">Assemble your team</h3>
          <p className="text-sm text-slate-600 dark:text-slate-300">Add agents by role and publish reusable team setups.</p>
        </article>
        <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/90">
          <p className="mb-2 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-brand-700 dark:text-slate-300">
            <ShieldCheck className="h-4 w-4" />
            Trust
          </p>
          <h3 className="mb-1 text-lg font-bold text-slate-900 dark:text-slate-50">Check reviews before install</h3>
          <p className="text-sm text-slate-600 dark:text-slate-300">Evaluate quality with ratings and user feedback.</p>
        </article>
      </div>
    </section>
  );
}
