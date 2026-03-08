"use client";

import { Check, Layers3, Search, Sparkles, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AgentCard } from "@/components/agents/agent-card";
import { Button } from "@/components/ui/button";
import {
  clearAccessToken,
  fetchCurrentUser,
  getAccessToken,
  type AuthUser
} from "@/lib/auth-client";
import {
  addTeamItem,
  createTeam,
  type Agent
} from "@/lib/api";
import { formatAuthLoading, t, type Locale } from "@/lib/i18n";

type CatalogTeamComposerProps = {
  initialAgents: Agent[];
  locale: Locale;
};

type SelectedAgent = {
  agent: Agent;
  roleName: string;
  isRequired: boolean;
};

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function buildDefaultRoleName(agent: Agent, selectedAgents: SelectedAgent[]): string {
  const category = agent.category?.trim().toLowerCase();
  let baseRole =
    category === "backend"
      ? "backend-developer"
      : category === "frontend"
        ? "frontend-developer"
        : category === "tooling"
          ? "tooling-specialist"
          : slugify(agent.slug);

  if (!baseRole) {
    baseRole = "team-agent";
  }

  const normalizedExistingRoles = new Set(
    selectedAgents.map((item) => item.roleName.trim().toLowerCase())
  );
  let candidate = baseRole;
  let suffix = 2;
  while (normalizedExistingRoles.has(candidate.toLowerCase())) {
    candidate = `${baseRole}-${suffix}`;
    suffix += 1;
  }
  return candidate;
}

function categoryLabel(category: string, locale: Locale) {
  return category === "all" ? t(locale, { ru: "Все", en: "All" }) : category;
}

export function CatalogTeamComposer({ initialAgents, locale }: CatalogTeamComposerProps) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loadingUser, setLoadingUser] = useState(false);

  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [selectedAgents, setSelectedAgents] = useState<SelectedAgent[]>([]);

  const [teamTitle, setTeamTitle] = useState("");
  const [teamSlug, setTeamSlug] = useState("");
  const [teamSlugTouched, setTeamSlugTouched] = useState(false);
  const [teamDescription, setTeamDescription] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function resolveUser() {
      const currentToken = getAccessToken();
      if (!currentToken) {
        if (!cancelled) {
          setUser(null);
          setToken(null);
          setLoadingUser(false);
        }
        return;
      }

      if (!cancelled) {
        setToken(currentToken);
        setLoadingUser(true);
      }

      try {
        const currentUser = await fetchCurrentUser(currentToken);
        if (!cancelled) {
          setUser(currentUser);
          setLoadingUser(false);
        }
      } catch {
        clearAccessToken();
        if (!cancelled) {
          setUser(null);
          setToken(null);
          setLoadingUser(false);
        }
      }
    }

    void resolveUser();

    return () => {
      cancelled = true;
    };
  }, []);

  const categories = useMemo(() => {
    const uniqueCategories = Array.from(
      new Set(
        initialAgents
          .map((agent) => agent.category?.trim())
          .filter((value): value is string => Boolean(value))
      )
    ).sort((left, right) => left.localeCompare(right));

    return ["all", ...uniqueCategories];
  }, [initialAgents]);

  const filteredAgents = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();

    return initialAgents.filter((agent) => {
      if (categoryFilter !== "all" && agent.category !== categoryFilter) {
        return false;
      }

      if (!normalizedSearch) {
        return true;
      }

      const haystack = `${agent.title} ${agent.slug} ${agent.short_description}`.toLowerCase();
      return haystack.includes(normalizedSearch);
    });
  }, [categoryFilter, initialAgents, search]);

  useEffect(() => {
    if (teamSlugTouched) {
      return;
    }
    setTeamSlug(slugify(teamTitle));
  }, [teamSlugTouched, teamTitle]);

  function toggleAgent(agent: Agent) {
    setSelectedAgents((current) => {
      const exists = current.some((item) => item.agent.id === agent.id);
      if (exists) {
        return current.filter((item) => item.agent.id !== agent.id);
      }

      return [
        ...current,
        {
          agent,
          roleName: buildDefaultRoleName(agent, current),
          isRequired: true
        }
      ];
    });
  }

  function updateSelectedAgent(
    agentId: string,
    patch: Partial<Pick<SelectedAgent, "roleName" | "isRequired">>
  ) {
    setSelectedAgents((current) =>
      current.map((item) => (item.agent.id === agentId ? { ...item, ...patch } : item))
    );
  }

  async function onCreateDraftTeam(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!token) {
      router.push("/auth/login");
      return;
    }

    if (selectedAgents.length === 0) {
      setErrorMessage(t(locale, { ru: "Выберите хотя бы одного агента из каталога.", en: "Select at least one agent from the catalog." }));
      return;
    }

    setSubmitting(true);
    setErrorMessage(null);

    let createdTeamSlug: string | null = null;

    try {
      const createdTeam = await createTeam(
        {
          slug: teamSlug.trim(),
          title: teamTitle.trim(),
          description: teamDescription.trim() || undefined
        },
        token
      );
      createdTeamSlug = createdTeam.slug;

      for (const [index, selected] of selectedAgents.entries()) {
        await addTeamItem(
          createdTeam.slug,
          {
            agent_slug: selected.agent.slug,
            role_name: selected.roleName.trim(),
            order_index: index,
            is_required: selected.isRequired
          },
          token
        );
      }

      router.push(`/teams/${createdTeam.slug}`);
      router.refresh();
    } catch (error) {
      if (createdTeamSlug) {
        setErrorMessage(
          t(locale, {
            ru: `Draft-команда '${createdTeamSlug}' создана, но выбранные агенты добавлены не полностью. Откройте страницу команды и завершите состав там.`,
            en: `Draft team '${createdTeamSlug}' was created, but selected agents were not fully added. Open the team page and finish composition there.`
          })
        );
      } else {
        setErrorMessage(
          error instanceof Error
            ? error.message
            : t(locale, {
                ru: "Не удалось создать draft-команду из выбранных агентов.",
                en: "Failed to create draft team from selected agents."
              })
        );
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="space-y-6">
      <section className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
        <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="flex items-center gap-2 text-2xl font-bold text-slate-900 dark:text-slate-50">
              <Layers3 className="h-5 w-5" />
              {t(locale, { ru: "Собрать draft-команду", en: "Build Draft Team" })}
            </h2>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
              {t(locale, {
                ru: "Выберите опубликованных агентов из каталога и создайте draft-команду, не покидая эту страницу.",
                en: "Select published agents from the catalog and create a draft team without leaving this page."
              })}
            </p>
          </div>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-600 dark:bg-zinc-800 dark:text-slate-200">
            {selectedAgents.length} {t(locale, { ru: "выбрано", en: "selected" })}
          </span>
        </div>

        {loadingUser ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">{formatAuthLoading(locale)}</p>
        ) : !user ? (
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5 text-sm text-slate-600 dark:border-zinc-800 dark:bg-zinc-900/70 dark:text-slate-300">
            {t(locale, {
              ru: "Войдите, чтобы создать draft-команду из выбранных агентов.",
              en: "Login to create a draft team from selected agents."
            })}
          </div>
        ) : (
          <form className="grid gap-6 xl:grid-cols-[0.95fr,1.05fr]" onSubmit={onCreateDraftTeam}>
            <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-5 dark:border-zinc-800 dark:bg-zinc-900/70">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
                {t(locale, { ru: "Настройки draft-команды", en: "Draft team settings" })}
              </h3>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                {t(locale, {
                  ru: "Выбранные агенты будут добавлены в draft-команду сразу. Роли можно изменить позже.",
                  en: "Selected agents will be added to the draft team right away. You can adjust roles later."
                })}
              </p>

              <div className="mt-4 space-y-4">
                <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                  {t(locale, { ru: "Название команды", en: "Team title" })}
                  <input
                    className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                    minLength={2}
                    onChange={(event) => setTeamTitle(event.target.value)}
                    required
                    type="text"
                    value={teamTitle}
                  />
                </label>

                <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                  {t(locale, { ru: "Slug команды", en: "Team slug" })}
                  <input
                    className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                    minLength={2}
                    onChange={(event) => {
                      setTeamSlugTouched(true);
                      setTeamSlug(event.target.value);
                    }}
                    required
                    type="text"
                    value={teamSlug}
                  />
                </label>

                <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                  {t(locale, { ru: "Описание", en: "Description" })}
                  <textarea
                    className="mt-1 min-h-28 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                    onChange={(event) => setTeamDescription(event.target.value)}
                    value={teamDescription}
                  />
                </label>

                {errorMessage ? (
                  <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
                    {errorMessage}
                  </p>
                ) : null}

                <Button
                  disabled={
                    submitting ||
                    selectedAgents.length === 0 ||
                    teamTitle.trim().length < 2 ||
                    teamSlug.trim().length < 2
                  }
                  type="submit"
                >
                  <Sparkles className="mr-2 h-4 w-4" />
                  {submitting
                    ? t(locale, { ru: "Создание...", en: "Creating..." })
                    : t(locale, { ru: "Создать draft-команду", en: "Create draft team" })}
                </Button>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-5 dark:border-zinc-800 dark:bg-zinc-900/70">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
                {t(locale, { ru: "Выбранные агенты", en: "Selected agents" })}
              </h3>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                {t(locale, {
                  ru: "Проверьте состав перед созданием черновика команды.",
                  en: "Review the composition before creating the team draft."
                })}
              </p>

              <div className="mt-4 space-y-3">
                {selectedAgents.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-slate-300 px-4 py-5 text-sm text-slate-500 dark:border-zinc-700 dark:text-slate-400">
                    {t(locale, {
                      ru: "Выберите агентов ниже, чтобы начать собирать команду.",
                      en: "Select agents below to start building a team."
                    })}
                  </div>
                ) : (
                  selectedAgents.map((item, index) => (
                    <div
                      className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
                      key={item.agent.id}
                    >
                      <div className="mb-3 flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">
                            {item.agent.title}
                          </p>
                          <p className="text-xs text-slate-500 dark:text-slate-400">
                            #{index} · {item.agent.slug}
                          </p>
                        </div>
                        <button
                          className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-zinc-800 dark:hover:text-slate-200"
                          onClick={() => toggleAgent(item.agent)}
                          type="button"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>

                      <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                        {t(locale, { ru: "Название роли", en: "Role name" })}
                        <input
                          className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                          minLength={2}
                          onChange={(event) =>
                            updateSelectedAgent(item.agent.id, { roleName: event.target.value })
                          }
                          required
                          type="text"
                          value={item.roleName}
                        />
                      </label>

                      <label className="mt-3 flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-200">
                        <input
                          checked={item.isRequired}
                          onChange={(event) =>
                            updateSelectedAgent(item.agent.id, { isRequired: event.target.checked })
                          }
                          type="checkbox"
                        />
                        {t(locale, { ru: "Обязательная роль", en: "Required role" })}
                      </label>
                    </div>
                  ))
                )}
              </div>
            </div>
          </form>
        )}
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-50">
              {t(locale, { ru: "Доступные агенты", en: "Available Agents" })}
            </h2>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
              {t(locale, {
                ru: "Выбирайте агентов из публичного каталога и добавляйте их в состав draft-команды.",
                en: "Choose agents from the public catalog, then add them into a draft team composition."
              })}
            </p>
          </div>

          <div className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-zinc-800 dark:bg-zinc-900/70">
            <Search className="h-4 w-4 text-slate-400" />
            <input
              className="w-56 bg-transparent text-sm outline-none placeholder:text-slate-400 dark:text-slate-100"
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t(locale, { ru: "Поиск по названию, slug и описанию", en: "Search title, slug, description" })}
              type="text"
              value={search}
            />
          </div>
        </div>

        <div className="mb-5 flex flex-wrap gap-2">
          {categories.map((category) => (
            <button
              className={`rounded-full px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] transition ${
                categoryFilter === category
                  ? "bg-brand-600 text-white dark:bg-slate-100 dark:text-slate-900"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-zinc-900 dark:text-slate-300 dark:hover:bg-zinc-800"
              }`}
              key={category}
              onClick={() => setCategoryFilter(category)}
              type="button"
            >
              {categoryLabel(category, locale)}
            </button>
          ))}
        </div>

        {filteredAgents.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 px-4 py-5 text-sm text-slate-500 dark:border-zinc-700 dark:text-slate-400">
            {t(locale, {
              ru: "Нет агентов, подходящих под текущий поиск и фильтр категории.",
              en: "No agents match the current search and category filter."
            })}
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filteredAgents.map((agent) => {
              const isSelected = selectedAgents.some((item) => item.agent.id === agent.id);

              return (
                <AgentCard
                  action={
                    <Button
                      onClick={() => toggleAgent(agent)}
                      size="sm"
                      type="button"
                      variant={isSelected ? "secondary" : "ghost"}
                    >
                      {isSelected ? (
                        <>
                          <Check className="mr-1 h-4 w-4" />
                          {t(locale, { ru: "Выбрано", en: "Selected" })}
                        </>
                      ) : (
                        t(locale, { ru: "Выбрать", en: "Select" })
                      )}
                    </Button>
                  }
                  agent={agent}
                  key={agent.id}
                  locale={locale}
                  selected={isSelected}
                />
              );
            })}
          </div>
        )}
      </section>
    </section>
  );
}
