"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { getAccessToken } from "@/lib/auth-client";
import { createTeam } from "@/lib/api";
import { t, type Locale } from "@/lib/i18n";

type CreateTeamFormProps = {
  locale: Locale;
};

export function CreateTeamForm({ locale }: CreateTeamFormProps) {
  const router = useRouter();

  const [slug, setSlug] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [startupPrompt, setStartupPrompt] = useState("");
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
          description: description.trim() || undefined,
          startup_prompt: startupPrompt.trim() || undefined
        },
        token
      );

      router.push(`/teams/${created.slug}`);
      router.refresh();
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : t(locale, { ru: "Не удалось создать команду.", en: "Failed to create team." })
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="mx-auto max-w-2xl rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <h1 className="mb-2 text-2xl font-black text-slate-900 dark:text-slate-50">{t(locale, { ru: "Создать команду", en: "Create Team" })}</h1>
      <p className="mb-6 text-sm text-slate-600 dark:text-slate-300">
        {t(locale, { ru: "Создайте draft-команду, соберите состав из доступных агентов и затем публикуйте готовую композицию.", en: "Create a draft team, assemble it from available agents, then publish once the composition is ready." })}
      </p>

      <form className="space-y-4" onSubmit={onSubmit}>
        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          Slug
          <input
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            minLength={2}
            onChange={(event) => setSlug(event.target.value)}
            placeholder="mvp-backend-team"
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
            placeholder="MVP Backend Team"
            required
            type="text"
            value={title}
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          {t(locale, { ru: "Описание", en: "Description" })}
          <textarea
            className="mt-1 min-h-24 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            onChange={(event) => setDescription(event.target.value)}
            placeholder={t(locale, { ru: "Цели команды и рабочий процесс.", en: "Team goals and workflow." })}
            value={description}
          />
        </label>

        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          {t(locale, { ru: "Стартовый runtime-промт", en: "Runtime startup prompt" })}
          <textarea
            className="mt-1 min-h-36 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            onChange={(event) => setStartupPrompt(event.target.value)}
            placeholder={t(locale, {
              ru: "Например: начни с роли orchestrator, при подходящей задаче делегируй backend/frontend роли и затем собери единый финальный результат.",
              en: "For example: start as the orchestrator, delegate to backend/frontend roles when useful, then merge the result into one final delivery."
            })}
            value={startupPrompt}
          />
          <p className="mt-1 text-xs font-normal text-slate-500 dark:text-slate-400">
            {t(locale, {
              ru: "Этот текст будет включён в стартовый prompt каждого run, запущенного этой командой.",
              en: "This text is injected into the initial prompt of every run launched with this team."
            })}
          </p>
        </label>

        {errorMessage ? (
          <p className="rounded-lg border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {errorMessage}
          </p>
        ) : null}

        <div className="flex items-center gap-3">
          <Button disabled={submitting} type="submit">
            {submitting ? t(locale, { ru: "Сохранение...", en: "Saving..." }) : t(locale, { ru: "Сохранить команду", en: "Save Team" })}
          </Button>
          <Link className="text-sm font-semibold text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-slate-100" href="/teams">
            {t(locale, { ru: "Отмена", en: "Cancel" })}
          </Link>
        </div>
      </form>
    </section>
  );
}
