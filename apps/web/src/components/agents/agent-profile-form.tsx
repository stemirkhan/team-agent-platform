"use client";

import { Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { clearAccessToken, fetchCurrentUser, getAccessToken, type AuthUser } from "@/lib/auth-client";
import { type Agent, type AgentMarkdownFile, type AgentSkill, updateAgent } from "@/lib/api";
import { formatAuthLoading, t, type Locale } from "@/lib/i18n";

type AgentProfileFormProps = {
  agent: Agent;
  locale: Locale;
};

function createEmptySkill(): AgentSkill {
  return { slug: "", description: "", content: "" };
}

function createEmptyMarkdownFile(): AgentMarkdownFile {
  return { path: "", content: "" };
}

function readNestedString(
  source: Record<string, unknown> | null | undefined,
  ...path: string[]
): string | null {
  let current: unknown = source;
  for (const key of path) {
    if (!current || typeof current !== "object") {
      return null;
    }
    current = (current as Record<string, unknown>)[key];
  }

  if (typeof current !== "string") {
    return null;
  }

  const normalized = current.trim();
  return normalized.length > 0 ? normalized : null;
}

export function AgentProfileForm({ agent, locale }: AgentProfileFormProps) {
  const router = useRouter();
  const manifest = useMemo(
    () =>
      agent.manifest_json && typeof agent.manifest_json === "object"
        ? agent.manifest_json
        : null,
    [agent.manifest_json]
  );

  const [user, setUser] = useState<AuthUser | null>(null);
  const [loadingAuth, setLoadingAuth] = useState(true);
  const [instructions, setInstructions] = useState(
    readNestedString(manifest, "instructions") ?? agent.install_instructions ?? agent.short_description
  );
  const [codexInstructions, setCodexInstructions] = useState(
    readNestedString(manifest, "codex", "developer_instructions") ??
      readNestedString(manifest, "instructions") ??
      agent.install_instructions ??
      agent.short_description
  );
  const [skills, setSkills] = useState<AgentSkill[]>(agent.skills ?? []);
  const [markdownFiles, setMarkdownFiles] = useState<AgentMarkdownFile[]>(agent.markdown_files ?? []);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function resolveUser() {
      const token = getAccessToken();
      if (!token) {
        if (!cancelled) {
          setUser(null);
          setLoadingAuth(false);
        }
        return;
      }

      try {
        const currentUser = await fetchCurrentUser(token);
        if (!cancelled) {
          setUser(currentUser);
          setLoadingAuth(false);
        }
      } catch {
        clearAccessToken();
        if (!cancelled) {
          setUser(null);
          setLoadingAuth(false);
        }
      }
    }

    void resolveUser();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setInstructions(
      readNestedString(manifest, "instructions") ??
        agent.install_instructions ??
        agent.short_description
    );
    setCodexInstructions(
      readNestedString(manifest, "codex", "developer_instructions") ??
        readNestedString(manifest, "instructions") ??
        agent.install_instructions ??
        agent.short_description
    );
    setSkills(agent.skills ?? []);
    setMarkdownFiles(agent.markdown_files ?? []);
  }, [agent, manifest]);

  function updateSkill(index: number, patch: Partial<AgentSkill>) {
    setSkills((current) =>
      current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item))
    );
  }

  function updateMarkdownFile(index: number, patch: Partial<AgentMarkdownFile>) {
    setMarkdownFiles((current) =>
      current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item))
    );
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const token = getAccessToken();
    if (!token) {
      router.push("/auth/login");
      return;
    }

    setSubmitting(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      await updateAgent(
        agent.slug,
        {
          manifest_json: {
            title: agent.title,
            description: agent.full_description ?? agent.short_description,
            instructions: instructions.trim(),
            codex: {
              description: agent.short_description,
              developer_instructions: codexInstructions.trim()
            }
          },
          export_targets: ["codex"],
          compatibility_matrix: { codex: true },
          install_instructions: instructions.trim(),
          skills: skills.filter((item) => item.slug.trim() || item.content.trim()),
          markdown_files: markdownFiles.filter((item) => item.path.trim() || item.content.trim())
        },
        token
      );
      setSuccessMessage(
        t(locale, {
          ru: "Текущий export-profile агента обновлен. Обновляю страницу.",
          en: "The current agent export profile was updated. Refreshing page."
        })
      );
      router.refresh();
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : t(locale, { ru: "Не удалось обновить текущий профиль агента.", en: "Failed to update the current agent profile." })
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="space-y-5 rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="space-y-2">
        <h2 className="text-xl font-bold text-slate-900 dark:text-slate-50">
          {t(locale, { ru: "Текущий профиль агента", en: "Current agent profile" })}
        </h2>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          {t(locale, {
            ru: "Редактируйте текущие runtime-инструкции, skills и markdown-файлы агента.",
            en: "Edit the current runtime instructions, skills, and markdown files for this agent."
          })}
        </p>
      </div>

      <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 dark:border-zinc-800 dark:bg-zinc-900/70">
        <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
          {t(locale, { ru: "Текущее наполнение", en: "Current assets" })}
        </p>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
              {t(locale, { ru: "Skills", en: "Skills" })}
            </p>
            {agent.skills.length === 0 ? (
              <p className="text-sm text-slate-600 dark:text-slate-300">
                {t(locale, { ru: "Skills пока нет.", en: "No skills yet." })}
              </p>
            ) : (
              <ul className="space-y-2 text-sm text-slate-600 dark:text-slate-300">
                {agent.skills.map((skill) => (
                  <li key={skill.slug} className="rounded-xl border border-slate-200 bg-white px-3 py-2 dark:border-zinc-800 dark:bg-zinc-950">
                    <p className="font-semibold text-slate-900 dark:text-slate-100">{skill.slug}</p>
                    {skill.description ? <p>{skill.description}</p> : null}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="space-y-2">
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
              {t(locale, { ru: "Markdown файлы", en: "Markdown files" })}
            </p>
            {agent.markdown_files.length === 0 ? (
              <p className="text-sm text-slate-600 dark:text-slate-300">
                {t(locale, { ru: "Markdown-файлов пока нет.", en: "No markdown files yet." })}
              </p>
            ) : (
              <ul className="space-y-2 text-sm text-slate-600 dark:text-slate-300">
                {agent.markdown_files.map((file) => (
                  <li key={file.path} className="rounded-xl border border-slate-200 bg-white px-3 py-2 dark:border-zinc-800 dark:bg-zinc-950">
                    <code className="text-xs text-slate-700 dark:text-slate-200">{file.path}</code>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {loadingAuth ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">{formatAuthLoading(locale)}</p>
      ) : !user ? (
        <p className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:border-zinc-800 dark:bg-zinc-900/70 dark:text-slate-300">
          {t(locale, {
            ru: "Войдите, чтобы редактировать текущий профиль агента.",
            en: "Login to edit the current agent profile."
          })}
        </p>
      ) : (
        <form className="space-y-5" onSubmit={onSubmit}>
          <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 dark:border-zinc-800 dark:bg-zinc-900/70">
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
              {t(locale, { ru: "Runtime-инструкции", en: "Runtime instructions" })}
            </p>

            <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
              {t(locale, { ru: "Общие инструкции", en: "General instructions" })}
              <textarea
                className="mt-1 min-h-28 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                onChange={(event) => setInstructions(event.target.value)}
                required
                value={instructions}
              />
            </label>

            <details className="rounded-2xl border border-slate-200 bg-white px-4 py-4 dark:border-zinc-800 dark:bg-zinc-950">
              <summary className="cursor-pointer list-none text-sm font-semibold text-slate-800 marker:hidden dark:text-slate-100">
                {t(locale, { ru: "Advanced settings", en: "Advanced settings" })}
              </summary>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                {t(locale, {
                  ru: "Переопределите инструкции отдельно для Codex, если нужен более точный runtime-профиль.",
                  en: "Override instructions specifically for Codex when the runtime profile needs extra detail."
                })}
              </p>

              <div className="mt-4">
                <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                  Codex
                  <textarea
                    className="mt-1 min-h-28 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                    onChange={(event) => setCodexInstructions(event.target.value)}
                    required
                    value={codexInstructions}
                  />
                </label>
              </div>
            </details>
          </div>

          <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 dark:border-zinc-800 dark:bg-zinc-900/70">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                {t(locale, { ru: "Skills", en: "Skills" })}
              </p>
              <Button onClick={() => setSkills((current) => [...current, createEmptySkill()])} type="button" variant="secondary">
                <Plus className="mr-2 h-4 w-4" />
                {t(locale, { ru: "Добавить skill", en: "Add skill" })}
              </Button>
            </div>

            {skills.length === 0 ? (
              <p className="text-sm text-slate-600 dark:text-slate-300">
                {t(locale, { ru: "Пока нет skills.", en: "No skills yet." })}
              </p>
            ) : (
              <div className="space-y-4">
                {skills.map((skill, index) => (
                  <div key={`${skill.slug}-${index}`} className="space-y-3 rounded-2xl border border-slate-200 bg-white px-4 py-4 dark:border-zinc-800 dark:bg-zinc-950">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                        {t(locale, { ru: "Skill", en: "Skill" })} #{index + 1}
                      </p>
                      <button
                        className="inline-flex items-center text-sm font-semibold text-rose-600 hover:text-rose-700"
                        onClick={() => setSkills((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                        type="button"
                      >
                        <Trash2 className="mr-1 h-4 w-4" />
                        {t(locale, { ru: "Удалить", en: "Remove" })}
                      </button>
                    </div>

                    <div className="grid gap-3 md:grid-cols-2">
                      <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                        Slug
                        <input
                          className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                          onChange={(event) => updateSkill(index, { slug: event.target.value })}
                          placeholder="backend-audit"
                          value={skill.slug}
                        />
                      </label>

                      <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                        {t(locale, { ru: "Описание", en: "Description" })}
                        <input
                          className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                          onChange={(event) => updateSkill(index, { description: event.target.value })}
                          value={skill.description ?? ""}
                        />
                      </label>
                    </div>

                    <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                      SKILL.md
                      <textarea
                        className="mt-1 min-h-32 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-mono dark:border-zinc-700 dark:bg-zinc-900"
                        onChange={(event) => updateSkill(index, { content: event.target.value })}
                        value={skill.content}
                      />
                    </label>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 dark:border-zinc-800 dark:bg-zinc-900/70">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                {t(locale, { ru: "Markdown файлы", en: "Markdown files" })}
              </p>
              <Button onClick={() => setMarkdownFiles((current) => [...current, createEmptyMarkdownFile()])} type="button" variant="secondary">
                <Plus className="mr-2 h-4 w-4" />
                {t(locale, { ru: "Добавить файл", en: "Add file" })}
              </Button>
            </div>

            {markdownFiles.length === 0 ? (
              <p className="text-sm text-slate-600 dark:text-slate-300">
                {t(locale, { ru: "Пока нет markdown-файлов.", en: "No markdown files yet." })}
              </p>
            ) : (
              <div className="space-y-4">
                {markdownFiles.map((file, index) => (
                  <div key={`${file.path}-${index}`} className="space-y-3 rounded-2xl border border-slate-200 bg-white px-4 py-4 dark:border-zinc-800 dark:bg-zinc-950">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                        {t(locale, { ru: "Markdown файл", en: "Markdown file" })} #{index + 1}
                      </p>
                      <button
                        className="inline-flex items-center text-sm font-semibold text-rose-600 hover:text-rose-700"
                        onClick={() => setMarkdownFiles((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                        type="button"
                      >
                        <Trash2 className="mr-1 h-4 w-4" />
                        {t(locale, { ru: "Удалить", en: "Remove" })}
                      </button>
                    </div>

                    <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                      {t(locale, { ru: "Путь файла", en: "File path" })}
                      <input
                        className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                        onChange={(event) => updateMarkdownFile(index, { path: event.target.value })}
                        placeholder="AGENTS.md"
                        value={file.path}
                      />
                    </label>

                    <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                      Markdown
                      <textarea
                        className="mt-1 min-h-32 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-mono dark:border-zinc-700 dark:bg-zinc-900"
                        onChange={(event) => updateMarkdownFile(index, { content: event.target.value })}
                        value={file.content}
                      />
                    </label>
                  </div>
                ))}
              </div>
            )}
          </div>

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

          <div className="flex flex-wrap items-center gap-2">
            <Button disabled={submitting} type="submit">
              {submitting
                ? t(locale, { ru: "Сохраняем профиль...", en: "Saving profile..." })
                : t(locale, { ru: "Сохранить профиль агента", en: "Save agent profile" })}
            </Button>
          </div>
        </form>
      )}
    </section>
  );
}
