"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { getAccessToken } from "@/lib/auth-client";
import { createAgent, publishAgent } from "@/lib/api";

export default function CreateAgentPage() {
  const router = useRouter();

  const [slug, setSlug] = useState("");
  const [title, setTitle] = useState("");
  const [shortDescription, setShortDescription] = useState("");
  const [fullDescription, setFullDescription] = useState("");
  const [category, setCategory] = useState("");
  const [publishNow, setPublishNow] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const token = getAccessToken();
    if (!token) {
      router.push("/auth/login");
      return;
    }

    setSubmitting(true);
    setErrorMessage(null);

    try {
      const created = await createAgent(
        {
          slug: slug.trim(),
          title: title.trim(),
          short_description: shortDescription.trim(),
          full_description: fullDescription.trim() || undefined,
          category: category.trim() || undefined
        },
        token
      );

      if (publishNow) {
        await publishAgent(created.slug, token);
      }

      router.push(`/agents/${created.slug}`);
      router.refresh();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to create agent.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="mx-auto max-w-2xl rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6 shadow-sm">
      <h1 className="mb-2 text-2xl font-black text-slate-900 dark:text-slate-50">Create Agent</h1>
      <p className="mb-6 text-sm text-slate-600 dark:text-slate-300">Create a draft and optionally publish it right away.</p>

      <form className="space-y-4" onSubmit={onSubmit}>
        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          Slug
          <input
            className="mt-1 w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm"
            minLength={2}
            onChange={(event) => setSlug(event.target.value)}
            placeholder="fastapi-reviewer"
            required
            type="text"
            value={slug}
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          Title
          <input
            className="mt-1 w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm"
            minLength={2}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="FastAPI Reviewer"
            required
            type="text"
            value={title}
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          Short description
          <textarea
            className="mt-1 min-h-24 w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm"
            minLength={10}
            onChange={(event) => setShortDescription(event.target.value)}
            placeholder="What this agent does and when it is useful."
            required
            value={shortDescription}
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          Full description
          <textarea
            className="mt-1 min-h-28 w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm"
            onChange={(event) => setFullDescription(event.target.value)}
            placeholder="Detailed usage notes (optional)."
            value={fullDescription}
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          Category
          <input
            className="mt-1 w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm"
            maxLength={120}
            onChange={(event) => setCategory(event.target.value)}
            placeholder="backend"
            type="text"
            value={category}
          />
        </label>

        <label className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-200">
          <input
            checked={publishNow}
            onChange={(event) => setPublishNow(event.target.checked)}
            type="checkbox"
          />
          Publish immediately after create
        </label>

        {errorMessage ? (
          <p className="rounded-lg border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {errorMessage}
          </p>
        ) : null}

        <div className="flex items-center gap-3">
          <Button disabled={submitting} type="submit">
            {submitting ? "Saving..." : "Save Agent"}
          </Button>
          <Link className="text-sm font-semibold text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-slate-100" href="/agents">
            Cancel
          </Link>
        </div>
      </form>
    </section>
  );
}
