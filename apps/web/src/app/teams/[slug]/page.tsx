import Link from "next/link";
import { notFound } from "next/navigation";

import { ReviewsSection } from "@/components/teams/reviews-section";
import { TeamBuilderControls } from "@/components/teams/team-builder-controls";
import { fetchTeam, fetchTeamReviews } from "@/lib/api";

export default async function TeamDetailsPage({ params }: { params: { slug: string } }) {
  try {
    const [team, reviews] = await Promise.all([fetchTeam(params.slug), fetchTeamReviews(params.slug)]);

    return (
      <section className="max-w-4xl space-y-6">
        <Link className="mb-4 inline-flex text-sm font-semibold text-brand-700 hover:text-brand-900" href="/teams">
          &larr; Back to teams
        </Link>

        <h1 className="mb-2 text-3xl font-black text-slate-900">{team.title}</h1>
        <p className="mb-6 text-slate-600">{team.description ?? "No description yet."}</p>

        <div className="mb-6 grid gap-3 rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-700 md:grid-cols-2">
          <p>
            <span className="font-semibold">Slug:</span> {team.slug}
          </p>
          <p>
            <span className="font-semibold">Status:</span> {team.status}
          </p>
          <p>
            <span className="font-semibold">Author:</span> {team.author_name}
          </p>
          <p>
            <span className="font-semibold">Items:</span> {team.items.length}
          </p>
        </div>

        <section className="rounded-2xl border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-xl font-bold text-slate-900">Team Items</h2>

          {team.items.length === 0 ? (
            <p className="text-sm text-slate-500">No items in this team yet.</p>
          ) : (
            <ul className="space-y-3">
              {team.items.map((item) => (
                <li
                  className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700"
                  key={item.id}
                >
                  <p>
                    <span className="font-semibold">Role:</span> {item.role_name}
                  </p>
                  <p>
                    <span className="font-semibold">Agent:</span> {item.agent_slug}
                  </p>
                  <p>
                    <span className="font-semibold">Order:</span> {item.order_index}
                  </p>
                  <p>
                    <span className="font-semibold">Required:</span> {item.is_required ? "yes" : "no"}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>

        <TeamBuilderControls teamSlug={team.slug} teamStatus={team.status} />
        <ReviewsSection initialReviews={reviews.items} teamSlug={team.slug} />
      </section>
    );
  } catch {
    notFound();
  }
}
