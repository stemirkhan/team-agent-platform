"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Star } from "lucide-react";

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

function getRatingLabel(value: number): string {
  if (value >= 5) {
    return "excellent";
  }
  if (value >= 4) {
    return "good";
  }
  if (value >= 3) {
    return "okay";
  }
  if (value >= 2) {
    return "weak";
  }
  return "poor";
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
    <section className="rounded-2xl border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-5">
      <h2 className="mb-4 text-xl font-bold text-slate-900 dark:text-slate-50">Reviews</h2>

      {reviews.length === 0 ? (
        <p className="mb-5 text-sm text-slate-500 dark:text-slate-400">No reviews yet.</p>
      ) : (
        <ul className="mb-6 space-y-3">
          {reviews.map((review) => (
            <li className="rounded-xl border border-slate-200 dark:border-zinc-700 bg-slate-50 dark:bg-zinc-800/70 p-4 text-sm text-slate-700 dark:text-slate-200" key={review.id}>
              <p className="mb-1 font-semibold text-slate-900 dark:text-slate-50">
                {review.user_display_name} · {review.rating}/5
              </p>
              <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">{formatDate(review.created_at)}</p>
              <p className="mb-2">{review.text ?? "No text review provided."}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                works: {review.works_as_expected ? "yes" : "no"} · outdated: {review.outdated_flag ? "yes" : "no"} ·
                unsafe: {review.unsafe_flag ? "yes" : "no"}
              </p>
            </li>
          ))}
        </ul>
      )}

      {!user ? (
        <p className="text-sm text-slate-600 dark:text-slate-300">Login to leave a review.</p>
      ) : (
        <form className="space-y-3" onSubmit={onSubmit}>
          <p className="text-sm text-slate-600 dark:text-slate-300">Signed in as {user.display_name}</p>

          <div>
            <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Rating</p>
            <div className="mt-1 flex items-center gap-1">
              {[1, 2, 3, 4, 5].map((starValue) => (
                <button
                  aria-label={`Set rating to ${starValue}`}
                  className="rounded-md p-1 transition hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                  key={starValue}
                  onClick={() => setRating(starValue)}
                  type="button"
                >
                  <Star
                    className={[
                      "h-5 w-5 transition",
                      starValue <= rating
                        ? "fill-amber-400 text-amber-400"
                        : "fill-transparent text-slate-300 dark:text-slate-600"
                    ].join(" ")}
                  />
                </button>
              ))}
              <span className="ml-2 text-xs font-semibold text-slate-600 dark:text-slate-300">
                {rating} - {getRatingLabel(rating)}
              </span>
            </div>
          </div>

          <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
            Review text (optional)
            <textarea
              className="mt-1 min-h-24 w-full rounded-lg border border-slate-300 dark:border-zinc-600 px-3 py-2 text-sm"
              onChange={(event) => setText(event.target.value)}
              placeholder="Share what worked and what did not."
              value={text}
            />
          </label>

          <label className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-200">
            <input
              checked={worksAsExpected}
              onChange={(event) => setWorksAsExpected(event.target.checked)}
              type="checkbox"
            />
            Works as expected
          </label>

          <label className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-200">
            <input
              checked={outdatedFlag}
              onChange={(event) => setOutdatedFlag(event.target.checked)}
              type="checkbox"
            />
            Mark as outdated
          </label>

          <label className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-200">
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
