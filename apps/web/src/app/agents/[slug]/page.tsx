import Link from "next/link";
import { notFound } from "next/navigation";

import { AddToTeamControls } from "@/components/agents/add-to-team-controls";
import { ReviewsSection } from "@/components/agents/reviews-section";
import { fetchAgent, fetchAgentReviews } from "@/lib/api";

export default async function AgentDetailsPage({ params }: { params: { slug: string } }) {
  try {
    const [agent, reviews] = await Promise.all([
      fetchAgent(params.slug),
      fetchAgentReviews(params.slug),
    ]);

    return (
      <section className="max-w-3xl space-y-6">
        <Link className="mb-4 inline-flex text-sm font-semibold text-brand-700 hover:text-brand-900" href="/agents">
          &larr; Back to catalog
        </Link>

        <h1 className="mb-2 text-3xl font-black text-slate-900 dark:text-slate-50">{agent.title}</h1>
        <p className="mb-6 text-slate-600 dark:text-slate-300">{agent.short_description}</p>

        <div className="mb-6 grid gap-3 rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 text-sm text-slate-700 dark:text-slate-200 md:grid-cols-2">
          <p>
            <span className="font-semibold">Slug:</span> {agent.slug}
          </p>
          <p>
            <span className="font-semibold">Category:</span> {agent.category ?? "general"}
          </p>
          <p>
            <span className="font-semibold">Status:</span> {agent.status}
          </p>
          <p>
            <span className="font-semibold">Verification:</span> {agent.verification_status}
          </p>
          <p>
            <span className="font-semibold">Author:</span> {agent.author_name}
          </p>
        </div>

        <article className="prose-slate max-w-none rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5">
          <h2>Full Description</h2>
          <p>{agent.full_description ?? "No full description yet."}</p>
        </article>

        <AddToTeamControls agentSlug={agent.slug} />
        <ReviewsSection agentSlug={agent.slug} initialReviews={reviews.items} />
      </section>
    );
  } catch {
    notFound();
  }
}
