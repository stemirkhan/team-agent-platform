"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Layers3,
  Pencil,
  PlaySquare,
  Save,
  ShieldCheck,
  Sparkles,
  UsersRound,
  X
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { ExportControls } from "@/components/exports/export-controls";
import { TeamBuilderControls } from "@/components/teams/team-builder-controls";
import { Button } from "@/components/ui/button";
import { fetchCurrentUser, getAccessToken, type AuthUser } from "@/lib/auth-client";
import { updateTeam, type TeamDetails } from "@/lib/api";
import { formatStatus, t, type Locale } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type TeamDetailShowcaseProps = {
  team: TeamDetails;
  locale: Locale;
};

type TeamPageTabId = "overview" | "composition" | "export";

type StartupPromptCardProps = {
  locale: Locale;
  team: TeamDetails;
  onTeamUpdated: (team: TeamDetails) => void;
};

function teamRuntimeLabel(locale: Locale): string {
  return t(locale, { ru: "выбирается при запуске", en: "selected per run" });
}

function StartupPromptCard({ locale, team, onTeamUpdated }: StartupPromptCardProps) {
  const router = useRouter();
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [draftValue, setDraftValue] = useState(team.startup_prompt ?? "");
  const [editing, setEditing] = useState(false);
  const [loadingUser, setLoadingUser] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    setDraftValue(team.startup_prompt ?? "");
    setEditing(false);
    setErrorMessage(null);
  }, [team.startup_prompt, team.updated_at]);

  useEffect(() => {
    let cancelled = false;
    const token = getAccessToken();

    if (!token) {
      setCurrentUser(null);
      setLoadingUser(false);
      return;
    }

    const currentToken = token;
    setLoadingUser(true);

    async function resolveUser() {
      try {
        const nextUser = await fetchCurrentUser(currentToken);
        if (!cancelled) {
          setCurrentUser(nextUser);
          setLoadingUser(false);
        }
      } catch {
        if (!cancelled) {
          setCurrentUser(null);
          setLoadingUser(false);
        }
      }
    }

    void resolveUser();

    return () => {
      cancelled = true;
    };
  }, []);

  const canEditStartupPrompt =
    team.status === "published" &&
    Boolean(team.author_id) &&
    currentUser?.id === team.author_id;

  async function onSaveStartupPrompt(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const token = getAccessToken();
    if (!token) {
      router.push("/auth/login");
      return;
    }

    setSaving(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const nextTeam = await updateTeam(
        team.slug,
        {
          startup_prompt: draftValue.trim() || null
        },
        token
      );
      onTeamUpdated(nextTeam);
      setEditing(false);
      setSuccessMessage(
        t(locale, {
          ru: "Стартовый промт команды обновлен.",
          en: "Team startup prompt updated."
        })
      );
      router.refresh();
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : t(locale, {
              ru: "Не удалось обновить стартовый промт команды.",
              en: "Failed to update the team startup prompt."
            })
      );
    } finally {
      setSaving(false);
    }
  }

  function onCancelEditing() {
    setDraftValue(team.startup_prompt ?? "");
    setEditing(false);
    setErrorMessage(null);
  }

  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-2">
          <PlaySquare className="h-4 w-4 text-slate-500 dark:text-slate-400" />
          <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
            {t(locale, { ru: "Стартовый runtime-промт", en: "Runtime startup prompt" })}
          </h2>
        </div>
        {canEditStartupPrompt ? (
          editing ? (
            <div className="flex items-center gap-2">
              <Button
                disabled={saving}
                onClick={onCancelEditing}
                size="sm"
                type="button"
                variant="ghost"
              >
                <X className="mr-2 h-4 w-4" />
                {t(locale, { ru: "Отмена", en: "Cancel" })}
              </Button>
              <Button form="team-startup-prompt-form" disabled={saving} size="sm" type="submit">
                <Save className="mr-2 h-4 w-4" />
                {saving
                  ? t(locale, { ru: "Сохранение...", en: "Saving..." })
                  : t(locale, { ru: "Сохранить", en: "Save" })}
              </Button>
            </div>
          ) : (
            <Button onClick={() => setEditing(true)} size="sm" type="button" variant="secondary">
              <Pencil className="mr-2 h-4 w-4" />
              {t(locale, { ru: "Изменить промт", en: "Edit prompt" })}
            </Button>
          )
        ) : null}
      </div>

      {editing ? (
        <form className="mt-4 space-y-4" id="team-startup-prompt-form" onSubmit={onSaveStartupPrompt}>
          <p className="text-sm leading-6 text-slate-600 dark:text-slate-300">
            {t(locale, {
              ru: "Этот стартовый промт добавляется в TASK.md и влияет на начальный runtime prompt для каждого нового run команды.",
              en: "This startup prompt is added to TASK.md and becomes part of the initial runtime prompt for every new team run."
            })}
          </p>
          <textarea
            className="min-h-[200px] w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 dark:border-zinc-700 dark:bg-zinc-900 dark:text-slate-100 dark:placeholder:text-slate-500"
            disabled={saving}
            onChange={(event) => setDraftValue(event.target.value)}
            placeholder={t(locale, {
              ru: "Например: Начни с orchestrator, разбей задачу на backend/frontend ветки и делегируй работу профильным ролям.",
              en: "For example: Start as the orchestrator, split the task into backend/frontend tracks, and delegate work to specialist roles."
            })}
            value={draftValue}
          />
        </form>
      ) : (
        <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-700 dark:text-slate-200">
          {team.startup_prompt ??
            t(locale, {
              ru: "Для этой команды стартовый промт пока не задан.",
              en: "No startup prompt has been configured for this team yet."
            })}
        </p>
      )}

      {team.status === "published" ? (
        <p className="mt-4 text-xs leading-6 text-slate-500 dark:text-slate-400">
          {canEditStartupPrompt
            ? t(locale, {
                ru: "Published-команду можно тонко подстроить через startup prompt без возврата к draft-композиции.",
                en: "Published teams can be tuned through the startup prompt without reopening the draft composition."
              })
            : loadingUser
              ? t(locale, {
                  ru: "Проверяем, доступно ли редактирование стартового промта для текущего пользователя.",
                  en: "Checking whether startup prompt editing is available for the current user."
                })
              : t(locale, {
                  ru: "После публикации состав команды остаётся locked; startup prompt может менять только автор команды.",
                  en: "After publish, the team composition stays locked; only the team author can update the startup prompt."
                })}
        </p>
      ) : null}

      {errorMessage ? (
        <p className="mt-3 rounded-2xl border border-rose-300/70 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200">
          {errorMessage}
        </p>
      ) : null}

      {successMessage ? (
        <p className="mt-3 rounded-2xl border border-emerald-300/70 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200">
          {successMessage}
        </p>
      ) : null}
    </div>
  );
}

export function TeamDetailShowcase({ team, locale }: TeamDetailShowcaseProps) {
  const [teamState, setTeamState] = useState(team);
  const [activeTab, setActiveTab] = useState<TeamPageTabId>("overview");

  useEffect(() => {
    setTeamState(team);
  }, [team]);

  const requiredItems = useMemo(
    () => teamState.items.filter((item) => item.is_required),
    [teamState.items]
  );
  const optionalItems = useMemo(
    () => teamState.items.filter((item) => !item.is_required),
    [teamState.items]
  );

  const mainTabs = [
    {
      id: "overview" as const,
      label: t(locale, { ru: "Overview", en: "Overview" }),
      note: t(locale, { ru: "состав и роли", en: "composition and roles" })
    },
    {
      id: "composition" as const,
      label: t(locale, { ru: "Composition", en: "Composition" }),
      note: t(locale, { ru: "редактирование draft", en: "edit draft" })
    },
    {
      id: "export" as const,
      label: t(locale, { ru: "Export", en: "Export" }),
      note: t(locale, { ru: "runtime bundle", en: "runtime bundle" })
    }
  ];

  const renderOverview = () => (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-6">
        <div className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-slate-500 dark:text-slate-400" />
            <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Описание команды", en: "Team summary" })}
            </h2>
          </div>
          <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-700 dark:text-slate-200">
            {teamState.description ??
              t(locale, {
                ru: "Описание команды пока не добавлено.",
                en: "No team description has been added yet."
            })}
          </p>
        </div>

        <StartupPromptCard locale={locale} onTeamUpdated={setTeamState} team={teamState} />

        <div className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <UsersRound className="h-4 w-4 text-slate-500 dark:text-slate-400" />
              <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "Состав команды", en: "Team lineup" })}
              </h2>
            </div>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-900 dark:text-slate-200 dark:ring-zinc-700">
              {teamState.items.length}
            </span>
          </div>

          {teamState.items.length === 0 ? (
            <div className="mt-4 rounded-2xl border border-dashed border-slate-300 px-4 py-6 text-sm text-slate-500 dark:border-zinc-700 dark:text-slate-400">
              {t(locale, {
                ru: "В этой команде пока нет агентов.",
                en: "This team does not have any agents yet."
              })}
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              {teamState.items
                .slice()
                .sort((left, right) => left.order_index - right.order_index)
                .map((item) => (
                  <article
                    className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4 dark:border-zinc-800 dark:bg-zinc-900/70"
                    key={item.id}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-full bg-slate-200 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-600 dark:bg-zinc-800 dark:text-slate-300">
                            #{item.order_index}
                          </span>
                          <span className="rounded-full bg-brand-100 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-700 dark:bg-brand-500/15 dark:text-brand-200">
                            {item.is_required
                              ? t(locale, { ru: "обязательная", en: "required" })
                              : t(locale, { ru: "опциональная", en: "optional" })}
                          </span>
                          <span className="rounded-full bg-slate-200 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-600 dark:bg-zinc-800 dark:text-slate-300">
                            {item.role_name}
                          </span>
                        </div>

                        <div>
                          <Link
                            className="text-lg font-semibold text-slate-900 transition hover:text-brand-700 dark:text-slate-100 dark:hover:text-white"
                            href={`/agents/${item.agent_slug}`}
                          >
                            {item.agent_title}
                          </Link>
                          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                            {item.agent_slug}
                          </p>
                        </div>
                      </div>

                      <Link
                        className="text-sm font-semibold text-brand-700 hover:text-brand-900 dark:text-slate-200 dark:hover:text-white"
                        href={`/agents/${item.agent_slug}`}
                      >
                        {t(locale, { ru: "Открыть агента", en: "Open agent" })}
                      </Link>
                    </div>

                    <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
                      {item.agent_short_description}
                    </p>
                  </article>
                ))}
            </div>
          )}
        </div>
      </div>

      <aside className="space-y-4 xl:sticky xl:top-24 xl:self-start">
        <div className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 dark:border-zinc-800 dark:bg-zinc-900/70">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-slate-500 dark:text-slate-400" />
            <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Профиль команды", en: "Team profile" })}
            </h3>
          </div>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex items-start justify-between gap-4">
              <dt className="text-slate-500 dark:text-slate-400">{t(locale, { ru: "Автор", en: "Author" })}</dt>
              <dd className="text-right font-semibold text-slate-900 dark:text-slate-100">{teamState.author_name}</dd>
            </div>
            <div className="flex items-start justify-between gap-4">
              <dt className="text-slate-500 dark:text-slate-400">{t(locale, { ru: "Slug", en: "Slug" })}</dt>
              <dd className="text-right font-semibold text-slate-900 dark:text-slate-100">{teamState.slug}</dd>
            </div>
            <div className="flex items-start justify-between gap-4">
              <dt className="text-slate-500 dark:text-slate-400">{t(locale, { ru: "Статус", en: "Status" })}</dt>
              <dd className="text-right font-semibold text-slate-900 dark:text-slate-100">
                {formatStatus(locale, teamState.status)}
              </dd>
            </div>
            <div className="flex items-start justify-between gap-4">
              <dt className="text-slate-500 dark:text-slate-400">{t(locale, { ru: "Runtime", en: "Runtime" })}</dt>
              <dd className="text-right font-semibold text-slate-900 dark:text-slate-100">{teamRuntimeLabel(locale)}</dd>
            </div>
            <div className="flex items-start justify-between gap-4">
              <dt className="text-slate-500 dark:text-slate-400">{t(locale, { ru: "Startup prompt", en: "Startup prompt" })}</dt>
              <dd className="text-right font-semibold text-slate-900 dark:text-slate-100">
                {teamState.startup_prompt
                  ? t(locale, { ru: "configured", en: "configured" })
                  : t(locale, { ru: "none", en: "none" })}
              </dd>
            </div>
          </dl>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex items-center gap-2">
            <Layers3 className="h-4 w-4 text-slate-500 dark:text-slate-400" />
            <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Сводка состава", en: "Composition summary" })}
            </h3>
          </div>
          <ul className="mt-4 space-y-3 text-sm text-slate-700 dark:text-slate-200">
            <li className="flex items-center justify-between gap-3">
              <span>{t(locale, { ru: "Всего ролей", en: "Total roles" })}</span>
              <span className="font-semibold">{teamState.items.length}</span>
            </li>
            <li className="flex items-center justify-between gap-3">
              <span>{t(locale, { ru: "Обязательные", en: "Required" })}</span>
              <span className="font-semibold">{requiredItems.length}</span>
            </li>
            <li className="flex items-center justify-between gap-3">
              <span>{t(locale, { ru: "Опциональные", en: "Optional" })}</span>
              <span className="font-semibold">{optionalItems.length}</span>
            </li>
          </ul>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex items-center gap-2">
            <PlaySquare className="h-4 w-4 text-slate-500 dark:text-slate-400" />
            <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Запуск команды", en: "Run team" })}
            </h3>
          </div>
          <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
            {t(locale, {
              ru: "Открой форму запуска и используй эту команду как execution-профиль для repo task.",
              en: "Open the run form and use this team as the execution profile for a repo task."
            })}
          </p>
          <div className="mt-4">
            <Link href={`/runs/new?team=${encodeURIComponent(teamState.slug)}`}>
              <Button variant="secondary">
                <PlaySquare className="mr-2 h-4 w-4" />
                {t(locale, { ru: "Запустить эту команду", en: "Run this team" })}
              </Button>
            </Link>
          </div>
        </div>
      </aside>
    </div>
  );

  return (
    <section className="space-y-6">
      <div className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
        <div className="border-b border-slate-200 bg-[linear-gradient(135deg,rgba(15,23,42,0.02),rgba(59,130,246,0.08),rgba(16,185,129,0.08))] px-6 py-8 dark:border-zinc-800 dark:bg-[linear-gradient(135deg,rgba(255,255,255,0.03),rgba(37,99,235,0.12),rgba(16,185,129,0.12))]">
          <div className="flex flex-col gap-8 xl:flex-row xl:items-start xl:justify-between">
            <div className="space-y-5">
              <div className="flex flex-wrap gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-950/90 dark:text-slate-200 dark:ring-zinc-700">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  {formatStatus(locale, teamState.status)}
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-950/90 dark:text-slate-200 dark:ring-zinc-700">
                  <UsersRound className="h-3.5 w-3.5" />
                  {teamState.items.length} {t(locale, { ru: "ролей", en: "roles" })}
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-950/90 dark:text-slate-200 dark:ring-zinc-700">
                  <Sparkles className="h-3.5 w-3.5" />
                  {teamRuntimeLabel(locale)}
                </span>
              </div>

              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-[0.32em] text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Team profile", en: "Team profile" })}
                </p>
                <h1 className="text-3xl font-black tracking-tight text-slate-950 dark:text-slate-50">
                  {teamState.title}
                </h1>
                <p className="max-w-3xl text-sm leading-7 text-slate-600 dark:text-slate-300">
                  {teamState.description ??
                    t(locale, {
                      ru: "Собранная команда агентов для локального runtime execution workflow.",
                      en: "An assembled agent team for the local runtime execution workflow."
                    })}
                </p>
              </div>

              <div className="flex flex-wrap gap-x-6 gap-y-3 text-sm">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">
                    {t(locale, { ru: "Автор", en: "Author" })}
                  </p>
                  <p className="font-semibold text-slate-900 dark:text-slate-100">{teamState.author_name}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">
                    {t(locale, { ru: "Slug", en: "Slug" })}
                  </p>
                  <p className="font-semibold text-slate-900 dark:text-slate-100">{teamState.slug}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">
                    {t(locale, { ru: "Runtime", en: "Runtime" })}
                  </p>
                  <p className="font-semibold text-slate-900 dark:text-slate-100">{teamRuntimeLabel(locale)}</p>
                </div>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3 xl:w-[320px] xl:grid-cols-1">
              <div className="rounded-2xl border border-slate-200 bg-white/90 px-4 py-4 dark:border-zinc-800 dark:bg-zinc-950/90">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Roles", en: "Roles" })}
                </p>
                <p className="mt-2 text-2xl font-black text-slate-950 dark:text-slate-50">{teamState.items.length}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white/90 px-4 py-4 dark:border-zinc-800 dark:bg-zinc-950/90">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Required", en: "Required" })}
                </p>
                <p className="mt-2 text-2xl font-black text-slate-950 dark:text-slate-50">
                  {requiredItems.length}
                </p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white/90 px-4 py-4 dark:border-zinc-800 dark:bg-zinc-950/90">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Runtime bundle", en: "Runtime bundle" })}
                </p>
                <p className="mt-2 text-sm font-semibold text-slate-900 dark:text-slate-100">
                  {t(locale, { ru: "командный runtime", en: "team runtime" })}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="border-b border-slate-200 px-6 py-4 dark:border-zinc-800">
          <div className="flex flex-wrap gap-2">
            {mainTabs.map((tab) => {
              const active = activeTab === tab.id;
              return (
                <button
                  className={cn(
                    "rounded-2xl border px-4 py-3 text-left transition",
                    active
                      ? "border-slate-300 bg-slate-950 text-slate-50 dark:border-zinc-700 dark:bg-slate-100 dark:text-slate-950"
                      : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 dark:border-zinc-800 dark:bg-zinc-950 dark:text-slate-200 dark:hover:border-zinc-700"
                  )}
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  type="button"
                >
                  <p className="text-sm font-semibold">{tab.label}</p>
                  <p
                    className={cn(
                      "mt-1 text-xs",
                      active ? "text-slate-300 dark:text-slate-600" : "text-slate-500 dark:text-slate-400"
                    )}
                  >
                    {tab.note}
                  </p>
                </button>
              );
            })}
          </div>
        </div>

        <div className="px-6 py-6">
          {activeTab === "overview" ? renderOverview() : null}
          {activeTab === "composition" ? <TeamBuilderControls locale={locale} team={teamState} /> : null}
          {activeTab === "export" ? (
            <ExportControls
              entityType="team"
              locale={locale}
              slug={teamState.slug}
              status={teamState.status}
            />
          ) : null}
        </div>
      </div>
    </section>
  );
}
