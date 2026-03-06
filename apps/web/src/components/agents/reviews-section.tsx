"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { clearAccessToken, fetchCurrentUser, getAccessToken, type AuthUser } from "@/lib/auth-client";
import { createAgentReview, type Review } from "@/lib/api";

type ReviewsSectionProps = {
  agentSlug: string;
  initialReviews: Review[];
};

function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString();
}

export function ReviewsSection({ agentSlug, initialReviews }: ReviewsSectionProps) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [reviews, setReviews] = useState<Review[]>(initialReviews);
  const [token, setToken] = useState<string | null>(null);

  const [rating, setRating] = useState(5);
  const [text, setText] = useState("");
  const [worksAsExpected, setWorksAsExpected] = useState(true);
  const [outdatedFlag, setOutdatedFlag] = useState(false);
  const [unsafeFlag, setUnsafeFlag] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function resolveUser() {
      const currentToken = getAccessToken();
      if (!currentToken) {
        if (!cancelled) {
          setUser(null);
          setToken(null);
        }
        return;
      }

      try {
        const currentUser = await fetchCurrentUser(currentToken);
        if (!cancelled) {
          setUser(currentUser);
          setToken(currentToken);
        }
      } catch {
        clearAccessToken();
        if (!cancelled) {
          setUser(null);
          setToken(null);
        }
      }
    }

    void resolveUser();

    return () => {
      cancelled = true;
    };
  }, []);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!token) {
      router.push("/auth/login");
      return;
    }

    setSubmitting(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const created = await createAgentReview(
        agentSlug,
        {
          rating,
          text: text.trim() || undefined,
          works_as_expected: worksAsExpected,
          outdated_flag: outdatedFlag,
          unsafe_flag: unsafeFlag
        },
        token
      );

      setReviews((previous) => [created, ...previous]);
      setText("");
      setRating(5);
      setWorksAsExpected(true);
      setOutdatedFlag(false);
      setUnsafeFlag(false);
      setSuccessMessage("Review submitted.");
      router.refresh();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to submit review.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5">
      <h2 className="mb-4 text-xl font-bold text-slate-900">Reviews</h2>

      {reviews.length === 0 ? (
        <p className="mb-5 text-sm text-slate-500">No reviews yet.</p>
      ) : (
        <ul className="mb-6 space-y-3">
          {reviews.map((review) => (
            <li className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700" key={review.id}>
              <p className="mb-1 font-semibold text-slate-900">
                {review.user_display_name} · {review.rating}/5
              </p>
              <p className="mb-2 text-xs text-slate-500">{formatDate(review.created_at)}</p>
              <p className="mb-2">{review.text ?? "No text review provided."}</p>
              <p className="text-xs text-slate-500">
                works: {review.works_as_expected ? "yes" : "no"} · outdated: {review.outdated_flag ? "yes" : "no"} ·
                unsafe: {review.unsafe_flag ? "yes" : "no"}
              </p>
            </li>
          ))}
        </ul>
      )}

      {!user ? (
        <p className="text-sm text-slate-600">Login to leave a review.</p>
      ) : (
        <form className="space-y-3" onSubmit={onSubmit}>
          <p className="text-sm text-slate-600">Signed in as {user.display_name}</p>

          <label className="block text-sm font-semibold text-slate-700">
            Rating
            <select
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
              onChange={(event) => setRating(Number(event.target.value))}
              value={rating}
            >
              <option value={5}>5 - excellent</option>
              <option value={4}>4 - good</option>
              <option value={3}>3 - okay</option>
              <option value={2}>2 - weak</option>
              <option value={1}>1 - poor</option>
            </select>
          </label>

          <label className="block text-sm font-semibold text-slate-700">
            Review text (optional)
            <textarea
              className="mt-1 min-h-24 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              onChange={(event) => setText(event.target.value)}
              placeholder="Share what worked and what did not."
              value={text}
            />
          </label>

          <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
            <input
              checked={worksAsExpected}
              onChange={(event) => setWorksAsExpected(event.target.checked)}
              type="checkbox"
            />
            Works as expected
          </label>

          <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
            <input
              checked={outdatedFlag}
              onChange={(event) => setOutdatedFlag(event.target.checked)}
              type="checkbox"
            />
            Mark as outdated
          </label>

          <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
            <input checked={unsafeFlag} onChange={(event) => setUnsafeFlag(event.target.checked)} type="checkbox" />
            Mark as potentially unsafe
          </label>

          {errorMessage ? (
            <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {errorMessage}
            </p>
          ) : null}

          {successMessage ? (
            <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
              {successMessage}
            </p>
          ) : null}

          <Button disabled={submitting} type="submit">
            {submitting ? "Submitting..." : "Submit Review"}
          </Button>
        </form>
      )}
    </section>
  );
}
