"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { getAccessToken } from "@/lib/auth-client";
import { createAgent, publishAgent } from "@/lib/api";
import { t, type Locale } from "@/lib/i18n";

type CreateAgentFormProps = {
  locale: Locale;
};

export function CreateAgentForm({ locale }: CreateAgentFormProps) {
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
      setErrorMessage(
        error instanceof Error ? error.message : t(locale, { ru: "Не удалось создать агента.", en: "Failed to create agent." })
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="mx-auto max-w-2xl rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <h1 className="mb-2 text-2xl font-black text-slate-900 dark:text-slate-50">{t(locale, { ru: "Создать агента", en: "Create Agent" })}</h1>
      <p className="mb-6 text-sm text-slate-600 dark:text-slate-300">
        {t(locale, { ru: "Создайте черновик и при необходимости сразу опубликуйте его.", en: "Create a draft and optionally publish it right away." })}
      </p>

      <form className="space-y-4" onSubmit={onSubmit}>
        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          Slug
          <input
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            minLength={2}
            onChange={(event) => setSlug(event.target.value)}
            placeholder="fastapi-reviewer"
            required
            type="text"
            value={slug}
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          {t(locale, { ru: "Название", en: "Title" })}
          <input
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            minLength={2}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="FastAPI Reviewer"
            required
            type="text"
            value={title}
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          {t(locale, { ru: "Краткое описание", en: "Short description" })}
          <textarea
            className="mt-1 min-h-24 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            minLength={10}
            onChange={(event) => setShortDescription(event.target.value)}
            placeholder={t(locale, { ru: "Что делает этот агент и когда он полезен.", en: "What this agent does and when it is useful." })}
            required
            value={shortDescription}
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          {t(locale, { ru: "Полное описание", en: "Full description" })}
          <textarea
            className="mt-1 min-h-28 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            onChange={(event) => setFullDescription(event.target.value)}
            placeholder={t(locale, { ru: "Подробные примечания по использованию (необязательно).", en: "Detailed usage notes (optional)." })}
            value={fullDescription}
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          {t(locale, { ru: "Категория", en: "Category" })}
          <input
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
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
          {t(locale, { ru: "Опубликовать сразу после создания", en: "Publish immediately after create" })}
        </label>

        {errorMessage ? (
          <p className="rounded-lg border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {errorMessage}
          </p>
        ) : null}

        <div className="flex items-center gap-3">
          <Button disabled={submitting} type="submit">
            {submitting ? t(locale, { ru: "Сохранение...", en: "Saving..." }) : t(locale, { ru: "Сохранить агента", en: "Save Agent" })}
          </Button>
          <Link className="text-sm font-semibold text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-slate-100" href="/agents">
            {t(locale, { ru: "Отмена", en: "Cancel" })}
          </Link>
        </div>
      </form>
    </section>
  );
}
