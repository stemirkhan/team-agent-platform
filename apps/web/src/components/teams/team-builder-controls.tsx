"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowDown,
  ArrowUp,
  Pencil,
  Plus,
  Save,
  Search,
  Trash2,
  X
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  clearAccessToken,
  fetchCurrentUser,
  getAccessToken,
  type AuthUser
} from "@/lib/auth-client";
import {
  addTeamItem,
  deleteTeamItem,
  fetchAgents,
  publishTeam,
  updateTeam,
  updateTeamItem,
  type Agent,
  type TeamDetails,
  type TeamItem
} from "@/lib/api";
import { formatAuthLoading, formatGeneralCategory, t, type Locale } from "@/lib/i18n";

type TeamBuilderControlsProps = {
  team: TeamDetails;
  locale: Locale;
};

function parseOptionalIndex(value: string): number | undefined {
  const normalized = value.trim();
  if (!normalized) {
    return undefined;
  }

  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) {
    return undefined;
  }

  return Math.max(0, Math.trunc(parsed));
}

export function TeamBuilderControls({ team, locale }: TeamBuilderControlsProps) {
  const router = useRouter();

  const [teamState, setTeamState] = useState(team);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loadingUser, setLoadingUser] = useState(false);

  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [agentSearch, setAgentSearch] = useState("");
  const [agentCategoryFilter, setAgentCategoryFilter] = useState("all");
  const [selectedAgentSlug, setSelectedAgentSlug] = useState("");

  const [settingsTitle, setSettingsTitle] = useState(team.title);
  const [settingsDescription, setSettingsDescription] = useState(team.description ?? "");
  const [settingsStartupPrompt, setSettingsStartupPrompt] = useState(team.startup_prompt ?? "");

  const [roleName, setRoleName] = useState("");
  const [isRequired, setIsRequired] = useState(true);
  const [orderIndex, setOrderIndex] = useState("");

  const [savingSettings, setSavingSettings] = useState(false);
  const [submittingItem, setSubmittingItem] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [removingItemId, setRemovingItemId] = useState<string | null>(null);
  const [movingItemId, setMovingItemId] = useState<string | null>(null);

  const [editingItemId, setEditingItemId] = useState<string | null>(null);
  const [editingAgentSlug, setEditingAgentSlug] = useState("");
  const [editingRoleName, setEditingRoleName] = useState("");
  const [editingOrderIndex, setEditingOrderIndex] = useState("");
  const [editingIsRequired, setEditingIsRequired] = useState(true);
  const [savingItem, setSavingItem] = useState(false);

  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    setTeamState(team);
    setSettingsTitle(team.title);
    setSettingsDescription(team.description ?? "");
    setSettingsStartupPrompt(team.startup_prompt ?? "");
    setEditingItemId(null);
  }, [team]);

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

  useEffect(() => {
    if (teamState.status !== "draft") {
      return;
    }

    let cancelled = false;
    setAgentsLoading(true);

    async function loadAgents() {
      try {
        const payload = await fetchAgents({ limit: 100, status: "published" });
        if (!cancelled) {
          setAgents(payload.items);
        }
      } catch {
        if (!cancelled) {
          setErrorMessage(t(locale, { ru: "Не удалось загрузить опубликованных агентов.", en: "Failed to load published agents." }));
        }
      } finally {
        if (!cancelled) {
          setAgentsLoading(false);
        }
      }
    }

    void loadAgents();

    return () => {
      cancelled = true;
    };
  }, [locale, teamState.status]);

  const canEditDraft = teamState.status === "draft" && Boolean(user);
  const selectedAgent = agents.find((agent) => agent.slug === selectedAgentSlug) ?? null;
  const agentCategories = useMemo(() => {
    const uniqueCategories = Array.from(
      new Set(
        agents
          .map((agent) => agent.category?.trim())
          .filter((value): value is string => Boolean(value))
      )
    ).sort((left, right) => left.localeCompare(right));

    return ["all", ...uniqueCategories];
  }, [agents]);
  const filteredAgents = useMemo(() => {
    const normalized = agentSearch.trim().toLowerCase();
    return agents
      .filter((agent) => {
        if (agentCategoryFilter !== "all" && agent.category !== agentCategoryFilter) {
          return false;
        }
        if (!normalized) {
          return true;
        }
        const haystack = `${agent.title} ${agent.slug} ${agent.short_description}`.toLowerCase();
        return haystack.includes(normalized);
      })
      .slice(0, 8);
  }, [agentCategoryFilter, agentSearch, agents]);

  function applyTeamState(nextTeam: TeamDetails, message: string) {
    setTeamState(nextTeam);
    setSettingsTitle(nextTeam.title);
    setSettingsDescription(nextTeam.description ?? "");
    setSettingsStartupPrompt(nextTeam.startup_prompt ?? "");
    setSuccessMessage(message);
    setErrorMessage(null);
    router.refresh();
  }

  function resetAddItemForm() {
    setAgentSearch("");
    setSelectedAgentSlug("");
    setRoleName("");
    setOrderIndex("");
    setIsRequired(true);
  }

  async function onSaveSettings(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!token) {
      router.push("/auth/login");
      return;
    }

    setSavingSettings(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const nextTeam = await updateTeam(
        teamState.slug,
        {
          title: settingsTitle.trim(),
          description: settingsDescription.trim() || null,
          startup_prompt: settingsStartupPrompt.trim() || null
        },
        token
      );
      applyTeamState(nextTeam, t(locale, { ru: "Настройки команды обновлены.", en: "Team settings updated." }));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t(locale, { ru: "Не удалось обновить команду.", en: "Failed to update team." }));
    } finally {
      setSavingSettings(false);
    }
  }

  async function onAddItem(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!token) {
      router.push("/auth/login");
      return;
    }
    if (!selectedAgentSlug) {
      setErrorMessage(t(locale, { ru: "Выберите агента перед добавлением элемента команды.", en: "Select an agent before adding a team item." }));
      return;
    }

    setSubmittingItem(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const nextTeam = await addTeamItem(
        teamState.slug,
        {
          agent_slug: selectedAgentSlug,
          role_name: roleName.trim(),
          order_index: parseOptionalIndex(orderIndex),
          is_required: isRequired
        },
        token
      );
      resetAddItemForm();
      applyTeamState(nextTeam, t(locale, { ru: "Элемент команды добавлен.", en: "Team item added." }));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t(locale, { ru: "Не удалось добавить элемент команды.", en: "Failed to add team item." }));
    } finally {
      setSubmittingItem(false);
    }
  }

  async function onPublishTeam() {
    if (!token) {
      router.push("/auth/login");
      return;
    }

    setPublishing(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const publishedTeam = await publishTeam(teamState.slug, token);
      setTeamState((current) => ({ ...current, ...publishedTeam }));
      setSuccessMessage(t(locale, { ru: "Команда опубликована.", en: "Team published." }));
      router.refresh();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t(locale, { ru: "Не удалось опубликовать команду.", en: "Failed to publish team." }));
    } finally {
      setPublishing(false);
    }
  }

  async function startEditingItem(item: TeamItem) {
    setEditingItemId(item.id);
    setEditingAgentSlug(item.agent_slug);
    setEditingRoleName(item.role_name);
    setEditingOrderIndex(String(item.order_index));
    setEditingIsRequired(item.is_required);
    setErrorMessage(null);
    setSuccessMessage(null);
  }

  function stopEditingItem() {
    setEditingItemId(null);
    setEditingAgentSlug("");
    setEditingRoleName("");
    setEditingOrderIndex("");
    setEditingIsRequired(true);
  }

  async function onSaveItem(itemId: string) {
    if (!token) {
      router.push("/auth/login");
      return;
    }
    if (!editingAgentSlug) {
      setErrorMessage(t(locale, { ru: "Выберите агента для элемента команды.", en: "Select an agent for the team item." }));
      return;
    }

    setSavingItem(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const nextTeam = await updateTeamItem(
        teamState.slug,
        itemId,
        {
          agent_slug: editingAgentSlug,
          role_name: editingRoleName.trim(),
          order_index: parseOptionalIndex(editingOrderIndex),
          is_required: editingIsRequired
        },
        token
      );
      stopEditingItem();
      applyTeamState(nextTeam, t(locale, { ru: "Элемент команды обновлен.", en: "Team item updated." }));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t(locale, { ru: "Не удалось обновить элемент команды.", en: "Failed to update team item." }));
    } finally {
      setSavingItem(false);
    }
  }

  async function onDeleteItem(itemId: string) {
    if (!token) {
      router.push("/auth/login");
      return;
    }

    setRemovingItemId(itemId);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const nextTeam = await deleteTeamItem(teamState.slug, itemId, token);
      if (editingItemId === itemId) {
        stopEditingItem();
      }
      applyTeamState(nextTeam, t(locale, { ru: "Элемент команды удален.", en: "Team item removed." }));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t(locale, { ru: "Не удалось удалить элемент команды.", en: "Failed to remove team item." }));
    } finally {
      setRemovingItemId(null);
    }
  }

  async function onMoveItem(item: TeamItem, direction: -1 | 1) {
    if (!token) {
      router.push("/auth/login");
      return;
    }

    const targetIndex = item.order_index + direction;
    if (targetIndex < 0 || targetIndex >= teamState.items.length) {
      return;
    }

    setMovingItemId(item.id);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const nextTeam = await updateTeamItem(
        teamState.slug,
        item.id,
        { order_index: targetIndex },
        token
      );
      applyTeamState(nextTeam, t(locale, { ru: "Порядок команды обновлен.", en: "Team order updated." }));
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t(locale, { ru: "Не удалось изменить порядок элементов команды.", en: "Failed to reorder team item." }));
    } finally {
      setMovingItemId(null);
    }
  }

  if (loadingUser) {
    return (
      <section className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
        <p className="text-sm text-slate-500 dark:text-slate-400">{formatAuthLoading(locale)}</p>
      </section>
    );
  }

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-50">
            {t(locale, { ru: "Состав команды", en: "Team Composition" })}
          </h2>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
            {t(locale, {
              ru: "Draft-команды собираются из текущих опубликованных агентов. Опубликованные команды остаются только для чтения и экспорта.",
              en: "Draft teams are assembled from current published agents. Published teams stay read-only and exportable."
            })}
          </p>
          {user ? (
            <p className="mt-2 text-xs font-medium uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">
              {t(locale, { ru: "Вы вошли как", en: "Signed in as" })} {user.display_name}
            </p>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Link
            className="text-sm font-semibold text-brand-700 hover:text-brand-900 dark:text-slate-200 dark:hover:text-white"
            href="/agents"
          >
            {t(locale, { ru: "Каталог агентов", en: "Browse agents" })}
          </Link>
          {teamState.status === "draft" ? (
            <Button
              disabled={publishing || teamState.items.length === 0}
              onClick={onPublishTeam}
              type="button"
              variant="secondary"
            >
              {publishing
                ? t(locale, { ru: "Публикация...", en: "Publishing..." })
                : t(locale, { ru: "Опубликовать команду", en: "Publish Team" })}
            </Button>
          ) : (
            <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-200">
              {t(locale, { ru: "Опубликовано", en: "Published" })}
            </span>
          )}
        </div>
      </div>

      {errorMessage ? (
        <p className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
          {errorMessage}
        </p>
      ) : null}

      {successMessage ? (
        <p className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200">
          {successMessage}
        </p>
      ) : null}

      <div className="space-y-4">
        {teamState.items.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 px-4 py-5 text-sm text-slate-500 dark:border-zinc-700 dark:text-slate-400">
            {t(locale, { ru: "В этой команде пока нет агентов.", en: "No agents in this team yet." })}
          </div>
        ) : (
          teamState.items.map((item) => {
            const isEditing = editingItemId === item.id;

            return (
              <article
                className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4 dark:border-zinc-800 dark:bg-zinc-900/70"
                key={item.id}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        className="text-lg font-semibold text-slate-900 transition hover:text-brand-700 dark:text-slate-100 dark:hover:text-white"
                        href={`/agents/${item.agent_slug}`}
                      >
                        {item.agent_title}
                      </Link>
                      <span className="rounded-full bg-slate-200 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-600 dark:bg-zinc-800 dark:text-slate-300">
                        #{item.order_index}
                      </span>
                      <span className="rounded-full bg-slate-200 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-600 dark:bg-zinc-800 dark:text-slate-300">
                        {t(locale, { ru: "роль", en: "role" })}: {item.role_name}
                      </span>
                      <span className="rounded-full bg-brand-100 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-700 dark:bg-brand-500/15 dark:text-brand-200">
                        {item.is_required
                          ? t(locale, { ru: "обязательная", en: "required" })
                          : t(locale, { ru: "опциональная", en: "optional" })}
                      </span>
                    </div>
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      {t(locale, { ru: "Исходный агент:", en: "Source agent:" })}{" "}
                      <Link
                        className="font-medium text-slate-600 transition hover:text-brand-700 dark:text-slate-300 dark:hover:text-white"
                        href={`/agents/${item.agent_slug}`}
                      >
                        {item.agent_slug}
                      </Link>
                    </p>
                  </div>

                  {canEditDraft ? (
                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        disabled={item.order_index === 0 || movingItemId === item.id}
                        onClick={() => void onMoveItem(item, -1)}
                        size="sm"
                        type="button"
                        variant="ghost"
                      >
                        <ArrowUp className="mr-1 h-4 w-4" />
                        {t(locale, { ru: "Вверх", en: "Up" })}
                      </Button>
                      <Button
                        disabled={
                          item.order_index === teamState.items.length - 1 || movingItemId === item.id
                        }
                        onClick={() => void onMoveItem(item, 1)}
                        size="sm"
                        type="button"
                        variant="ghost"
                      >
                        <ArrowDown className="mr-1 h-4 w-4" />
                        {t(locale, { ru: "Вниз", en: "Down" })}
                      </Button>
                      {isEditing ? (
                        <Button onClick={stopEditingItem} size="sm" type="button" variant="ghost">
                          <X className="mr-1 h-4 w-4" />
                          {t(locale, { ru: "Отмена", en: "Cancel" })}
                        </Button>
                      ) : (
                        <Button
                          onClick={() => void startEditingItem(item)}
                          size="sm"
                          type="button"
                          variant="ghost"
                        >
                          <Pencil className="mr-1 h-4 w-4" />
                          {t(locale, { ru: "Изменить", en: "Edit" })}
                        </Button>
                      )}
                      <Button
                        disabled={removingItemId === item.id}
                        onClick={() => void onDeleteItem(item.id)}
                        size="sm"
                        type="button"
                        variant="ghost"
                      >
                        <Trash2 className="mr-1 h-4 w-4" />
                        {removingItemId === item.id
                          ? t(locale, { ru: "Удаление...", en: "Removing..." })
                          : t(locale, { ru: "Удалить", en: "Remove" })}
                      </Button>
                    </div>
                  ) : null}
                </div>

                {isEditing ? (
                  <div className="mt-4 grid gap-4 md:grid-cols-2">
                    <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                      {t(locale, { ru: "Агент", en: "Agent" })}
                      <select
                        className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                        disabled={savingItem}
                        onChange={(event) => setEditingAgentSlug(event.target.value)}
                        value={editingAgentSlug}
                      >
                        <option value="">{t(locale, { ru: "Выберите агента", en: "Select an agent" })}</option>
                        {agents.map((agent) => (
                          <option key={agent.id} value={agent.slug}>
                            {agent.title} ({agent.slug})
                          </option>
                        ))}
                      </select>
                    </label>

                    <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                      {t(locale, { ru: "Название роли", en: "Role name" })}
                      <input
                        className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                        minLength={2}
                        onChange={(event) => setEditingRoleName(event.target.value)}
                        required
                        type="text"
                        value={editingRoleName}
                      />
                    </label>

                    <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                      {t(locale, { ru: "Порядковый индекс", en: "Order index" })}
                      <input
                        className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                        min={0}
                        onChange={(event) => setEditingOrderIndex(event.target.value)}
                        type="number"
                        value={editingOrderIndex}
                      />
                    </label>

                    <label className="flex items-center gap-2 self-end text-sm font-medium text-slate-700 dark:text-slate-200">
                      <input
                        checked={editingIsRequired}
                        onChange={(event) => setEditingIsRequired(event.target.checked)}
                        type="checkbox"
                      />
                      {t(locale, { ru: "Обязательная роль", en: "Required role" })}
                    </label>

                    <div className="md:col-span-2">
                      <Button
                        disabled={savingItem}
                        onClick={() => void onSaveItem(item.id)}
                        type="button"
                      >
                        <Save className="mr-2 h-4 w-4" />
                        {savingItem
                          ? t(locale, { ru: "Сохранение...", en: "Saving..." })
                          : t(locale, { ru: "Сохранить элемент", en: "Save item" })}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
                    {item.agent_short_description}
                  </p>
                )}
              </article>
            );
          })
        )}
      </div>

      {teamState.status !== "draft" ? (
        <p className="mt-6 text-sm text-slate-500 dark:text-slate-400">
          {t(locale, {
            ru: "Опубликованные команды неизменяемы. Создайте или обновите draft-команду, если нужно изменить состав.",
            en: "Published teams are immutable. Create or update a draft team if you need to change its composition."
          })}
        </p>
      ) : !user ? (
        <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-5 text-sm text-slate-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-slate-300">
          {t(locale, {
            ru: "Войдите, чтобы управлять настройками команды, добавлять агентов и публиковать этот draft.",
            en: "Login to manage team settings, add agents, and publish this draft."
          })}
        </div>
      ) : (
        <div className="mt-8 grid gap-6 xl:grid-cols-[0.95fr,1.05fr]">
          <form
            className="rounded-2xl border border-slate-200 bg-slate-50/80 p-5 dark:border-zinc-800 dark:bg-zinc-900/70"
            onSubmit={(event) => void onSaveSettings(event)}
          >
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
              {t(locale, { ru: "Настройки команды", en: "Team settings" })}
            </h3>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Обновите метаданные draft-команды перед публикацией.", en: "Update draft metadata before publishing." })}
            </p>

            <div className="mt-4 space-y-4">
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t(locale, { ru: "Название", en: "Title" })}
                <input
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  minLength={2}
                  onChange={(event) => setSettingsTitle(event.target.value)}
                  required
                  type="text"
                  value={settingsTitle}
                />
              </label>

              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t(locale, { ru: "Описание", en: "Description" })}
                <textarea
                  className="mt-1 min-h-28 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  onChange={(event) => setSettingsDescription(event.target.value)}
                  value={settingsDescription}
                />
              </label>

              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t(locale, { ru: "Стартовый runtime-промт", en: "Runtime startup prompt" })}
                <textarea
                  className="mt-1 min-h-36 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  onChange={(event) => setSettingsStartupPrompt(event.target.value)}
                  placeholder={t(locale, {
                    ru: "Например: сначала действуй как orchestrator, при необходимости делегируй backend/frontend ролям и затем собери единый результат.",
                    en: "For example: begin as the orchestrator, delegate to backend/frontend roles when needed, then merge the work into one final result."
                  })}
                  value={settingsStartupPrompt}
                />
                <p className="mt-1 text-xs font-normal text-slate-500 dark:text-slate-400">
                  {t(locale, {
                    ru: "Этот текст будет вставлен в стартовый prompt каждого run для этой команды.",
                    en: "This text is inserted into the initial prompt of every run for this team."
                  })}
                </p>
              </label>

              <Button disabled={savingSettings} type="submit" variant="secondary">
                {savingSettings
                  ? t(locale, { ru: "Сохранение...", en: "Saving..." })
                  : t(locale, { ru: "Сохранить настройки", en: "Save settings" })}
              </Button>
            </div>
          </form>

          <form
            className="rounded-2xl border border-slate-200 bg-slate-50/80 p-5 dark:border-zinc-800 dark:bg-zinc-900/70"
            onSubmit={(event) => void onAddItem(event)}
          >
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50">
              {t(locale, { ru: "Добавить агента", en: "Add agent" })}
            </h3>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {t(locale, {
                ru: "Найдите и отфильтруйте доступных агентов, затем добавьте нужного агента в эту команду.",
                en: "Search and filter available agents, then add the agent you need into this team."
              })}
            </p>

            <div className="mt-4 space-y-4">
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4 dark:border-zinc-800 dark:bg-zinc-950">
                <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-50">
                      {t(locale, { ru: "Доступные агенты", en: "Available agents" })}
                    </h4>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {t(locale, {
                        ru: "Выберите агента из опубликованного каталога.",
                        en: "Pick an agent from the published catalog."
                      })}
                    </p>
                  </div>
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-600 dark:bg-zinc-800 dark:text-slate-300">
                    {filteredAgents.length} {t(locale, { ru: "совпадений", en: "matches" })}
                  </span>
                </div>

                <div className="mb-3 flex flex-wrap gap-2">
                  {agentCategories.map((category) => (
                    <button
                      className={`rounded-full px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] transition ${
                        agentCategoryFilter === category
                          ? "bg-brand-600 text-white dark:bg-slate-100 dark:text-slate-900"
                          : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-zinc-900 dark:text-slate-300 dark:hover:bg-zinc-800"
                      }`}
                      key={category}
                      onClick={() => setAgentCategoryFilter(category)}
                      type="button"
                    >
                      {category === "all" ? t(locale, { ru: "Все", en: "All" }) : category}
                    </button>
                  ))}
                </div>

                <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                  {t(locale, { ru: "Поиск опубликованных агентов", en: "Search published agents" })}
                  <div className="relative mt-1">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    <input
                      className="w-full rounded-xl border border-slate-300 bg-white py-2 pl-10 pr-3 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                      onChange={(event) => {
                        setAgentSearch(event.target.value);
                        setSelectedAgentSlug("");
                      }}
                      placeholder={t(locale, { ru: "Найти по названию или slug", en: "Find by title or slug" })}
                      type="text"
                      value={agentSearch}
                    />
                  </div>
                </label>

                <div className="mt-4 space-y-2">
                  {agentsLoading ? (
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      {t(locale, { ru: "Загрузка опубликованных агентов...", en: "Loading published agents..." })}
                    </p>
                  ) : filteredAgents.length === 0 ? (
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      {t(locale, {
                        ru: "Нет агентов, подходящих под текущий поиск и фильтр категории.",
                        en: "No agents match the current search and category filter."
                      })}
                    </p>
                  ) : (
                    filteredAgents.map((agent) => (
                      <button
                        className={`w-full rounded-2xl border px-3 py-3 text-left transition ${
                          selectedAgentSlug === agent.slug
                            ? "border-brand-500 bg-brand-50 dark:border-brand-400 dark:bg-brand-500/10"
                            : "border-slate-200 bg-white hover:border-slate-300 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:border-zinc-700"
                        }`}
                        key={agent.id}
                        onClick={() => {
                          setSelectedAgentSlug(agent.slug);
                          setAgentSearch(`${agent.title} (${agent.slug})`);
                        }}
                        type="button"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">
                            {agent.title}
                          </p>
                          <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-600 dark:bg-zinc-800 dark:text-slate-300">
                            {agent.category ?? formatGeneralCategory(locale)}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400">{agent.slug}</p>
                        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                          {agent.short_description}
                        </p>
                      </button>
                    ))
                  )}
                </div>
              </div>

              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t(locale, { ru: "Выбранный агент", en: "Selected agent" })}
                <input
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  readOnly
                  type="text"
                  value={selectedAgent ? `${selectedAgent.title} (${selectedAgent.slug})` : ""}
                />
              </label>

              {selectedAgent ? (
                <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950">
                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-50">
                    {t(locale, { ru: "Выбрано:", en: "Selected:" })} {selectedAgent.title}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {selectedAgent.slug}
                  </p>
                  <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                    {selectedAgent.short_description}
                  </p>
                </div>
              ) : null}

              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t(locale, { ru: "Название роли", en: "Role name" })}
                <input
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  minLength={2}
                  onChange={(event) => setRoleName(event.target.value)}
                  placeholder="reviewer"
                  required
                  type="text"
                  value={roleName}
                />
              </label>

              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t(locale, { ru: "Порядковый индекс (необязательно)", en: "Order index (optional)" })}
                <input
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  min={0}
                  onChange={(event) => setOrderIndex(event.target.value)}
                  placeholder={t(locale, { ru: "Добавить в конец", en: "Append to the end" })}
                  type="number"
                  value={orderIndex}
                />
              </label>

              <label className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-200">
                <input
                  checked={isRequired}
                  onChange={(event) => setIsRequired(event.target.checked)}
                  type="checkbox"
                />
                {t(locale, { ru: "Обязательная роль", en: "Required role" })}
              </label>

              <Button
                disabled={submittingItem || !selectedAgentSlug}
                type="submit"
              >
                <Plus className="mr-2 h-4 w-4" />
                {submittingItem
                  ? t(locale, { ru: "Добавление...", en: "Adding..." })
                  : t(locale, { ru: "Добавить элемент команды", en: "Add team item" })}
              </Button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}
