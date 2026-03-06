"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { getAccessToken } from "@/lib/auth-client";
import { createTeam, publishTeam } from "@/lib/api";

export default function CreateTeamPage() {
  const router = useRouter();

  const [slug, setSlug] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [publishNow, setPublishNow] = useState(false);
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
      const created = await createTeam(
        {
          slug: slug.trim(),
          title: title.trim(),
          description: description.trim() || undefined
        },
        token
      );

      if (publishNow) {
        await publishTeam(created.slug, token);
      }

      router.push(`/teams/${created.slug}`);
      router.refresh();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to create team.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="mx-auto max-w-2xl rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6 shadow-sm">
      <h1 className="mb-2 text-2xl font-black text-slate-900 dark:text-slate-50">Create Team</h1>
      <p className="mb-6 text-sm text-slate-600 dark:text-slate-300">Create a team and optionally publish it.</p>

      <form className="space-y-4" onSubmit={onSubmit}>
        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          Slug
          <input
            className="mt-1 w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm"
            minLength={2}
            onChange={(event) => setSlug(event.target.value)}
            placeholder="mvp-backend-team"
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
            placeholder="MVP Backend Team"
            required
            type="text"
            value={title}
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          Description
          <textarea
            className="mt-1 min-h-24 w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm"
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Team goals and workflow."
            value={description}
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
            {submitting ? "Saving..." : "Save Team"}
          </Button>
          <Link className="text-sm font-semibold text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-slate-100" href="/teams">
            Cancel
          </Link>
        </div>
      </form>
    </section>
  );
}
