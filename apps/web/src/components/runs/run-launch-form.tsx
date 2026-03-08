"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Loader2, Play, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  clearAccessToken,
  fetchCurrentUser,
  getAccessToken,
  type AuthUser
} from "@/lib/auth-client";
import {
  createRun,
  type CodexReasoningEffort,
  type CodexSandboxMode,
  type GitHubRepo,
  type HostExecutionReadiness,
  type Team
} from "@/lib/api";
import { formatAuthLoading, t, type Locale } from "@/lib/i18n";

type RunLaunchFormProps = {
  locale: Locale;
  teams: Team[];
  suggestedRepos: GitHubRepo[];
  readiness: HostExecutionReadiness | null;
  initialOwner?: string;
  initialRepo?: string;
  initialIssueNumber?: number;
  initialTeamSlug?: string;
};

function parseIssueNumber(value: string): number | undefined {
  const normalized = value.trim();
  if (!normalized) {
    return undefined;
  }

  const parsed = Number(normalized);
  if (!Number.isFinite(parsed) || parsed < 1) {
    return undefined;
  }

  return Math.trunc(parsed);
}

export function RunLaunchForm({
  locale,
  teams,
  suggestedRepos,
  readiness,
  initialOwner,
  initialRepo,
  initialIssueNumber,
  initialTeamSlug
}: RunLaunchFormProps) {
  const router = useRouter();

  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loadingUser, setLoadingUser] = useState(true);

  const [teamSlug, setTeamSlug] = useState(initialTeamSlug ?? teams[0]?.slug ?? "");
  const [repoOwner, setRepoOwner] = useState(initialOwner ?? suggestedRepos[0]?.owner ?? "");
  const [repoName, setRepoName] = useState(initialRepo ?? suggestedRepos[0]?.name ?? "");
  const [baseBranch, setBaseBranch] = useState("");
  const [issueNumber, setIssueNumber] = useState(initialIssueNumber ? String(initialIssueNumber) : "");
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [taskText, setTaskText] = useState("");
  const [codexModel, setCodexModel] = useState("");
  const [reasoningEffort, setReasoningEffort] = useState<CodexReasoningEffort>("medium");
  const [sandboxMode, setSandboxMode] = useState<CodexSandboxMode>("workspace-write");
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function resolveUser() {
      const currentToken = getAccessToken();
      if (!currentToken) {
        if (!cancelled) {
          setToken(null);
          setUser(null);
          setLoadingUser(false);
        }
        return;
      }

      if (!cancelled) {
        setToken(currentToken);
      }

      try {
        const currentUser = await fetchCurrentUser(currentToken);
        if (!cancelled) {
          setUser(currentUser);
        }
      } catch {
        clearAccessToken();
        if (!cancelled) {
          setToken(null);
          setUser(null);
        }
      } finally {
        if (!cancelled) {
          setLoadingUser(false);
        }
      }
    }

    void resolveUser();

    return () => {
      cancelled = true;
    };
  }, []);

  const selectedRepo = useMemo(
    () => suggestedRepos.find((repo) => repo.owner === repoOwner && repo.name === repoName) ?? null,
    [repoName, repoOwner, suggestedRepos]
  );

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!token) {
      router.push("/auth/login");
      return;
    }

    if (!teamSlug || !repoOwner.trim() || !repoName.trim()) {
      setErrorMessage(
        t(locale, {
          ru: "Выбери команду и укажи GitHub owner/repo перед запуском.",
          en: "Select a team and provide the GitHub owner/repo before starting the run."
        })
      );
      return;
    }

    if (!issueNumber.trim() && !taskText.trim()) {
      setErrorMessage(
        t(locale, {
          ru: "Нужен либо issue number, либо ручное описание задачи.",
          en: "You need either an issue number or a manual task description."
        })
      );
      return;
    }

    if (readiness && !readiness.effective_ready) {
      setErrorMessage(
        t(locale, {
          ru: "Host execution пока не готов. Сначала исправь диагностику и затем повтори запуск.",
          en: "Host execution is not ready yet. Fix diagnostics first and then retry the run."
        })
      );
      return;
    }

    setSubmitting(true);
    setErrorMessage(null);

    try {
      const run = await createRun(
        {
          team_slug: teamSlug,
          repo_owner: repoOwner.trim(),
          repo_name: repoName.trim(),
          base_branch: baseBranch.trim() || undefined,
          issue_number: parseIssueNumber(issueNumber),
          task_text: taskText.trim() || undefined,
          title: title.trim() || undefined,
          summary: summary.trim() || undefined,
          codex: {
            model: codexModel.trim() || undefined,
            model_reasoning_effort: reasoningEffort,
            sandbox_mode: sandboxMode
          }
        },
        token
      );

      router.push(`/runs/${run.id}`);
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : t(locale, { ru: "Не удалось создать run.", en: "Failed to create run." })
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="space-y-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-black text-slate-900 dark:text-slate-50">
            {t(locale, { ru: "Новый запуск", en: "New run" })}
          </h2>
          <p className="mt-1 max-w-3xl text-sm text-slate-600 dark:text-slate-300">
            {t(locale, {
              ru: "Этот flow уже создает workspace, пишет `.codex/` и `TASK.md`, а затем стартует host-side `codex exec` в PTY-сессии.",
              en: "This flow already creates the workspace, writes `.codex/` and `TASK.md`, and then starts host-side `codex exec` in a PTY session."
            })}
          </p>
        </div>
        <Link
          className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-200 dark:bg-zinc-900/70 dark:text-slate-200 dark:hover:bg-zinc-800"
          href="/diagnostics"
        >
          <Sparkles className="h-3.5 w-3.5" />
          {t(locale, { ru: "Открыть диагностику", en: "Open diagnostics" })}
        </Link>
      </div>

      {loadingUser ? (
        <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3 text-sm text-slate-500 dark:border-zinc-800 dark:bg-zinc-900/70 dark:text-slate-400">
          {formatAuthLoading(locale)}
        </div>
      ) : null}

      {!loadingUser && !user ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200">
          <p>
            {t(locale, {
              ru: "Для запуска нужен вход в платформу. Сначала авторизуйся, затем повтори запуск.",
              en: "You need to sign in before starting a run. Sign in first and then retry."
            })}
          </p>
        </div>
      ) : null}

      {readiness && !readiness.effective_ready ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-200">
          {t(locale, {
            ru: "Host execution сейчас не готов. Открой диагностику и исправь `git` / `gh` / `codex` до запуска run.",
            en: "Host execution is not ready right now. Open diagnostics and fix `git` / `gh` / `codex` before starting a run."
          })}
        </div>
      ) : null}

      {errorMessage ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-200">
          {errorMessage}
        </div>
      ) : null}

      {teams.length === 0 ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200">
          {t(locale, {
            ru: "Опубликованных команд пока нет. Сначала собери и опубликуй хотя бы одну команду.",
            en: "There are no published teams yet. Create and publish at least one team first."
          })}
        </div>
      ) : null}

      <form className="space-y-6" onSubmit={onSubmit}>
        <div className="grid gap-5 lg:grid-cols-2">
          <div className="space-y-5 rounded-2xl border border-slate-200 bg-slate-50/70 p-4 dark:border-zinc-800 dark:bg-zinc-900/70">
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "Команда и репозиторий", en: "Team and repository" })}
              </h3>
            </div>

            <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
              {t(locale, { ru: "Команда", en: "Team" })}
              <select
                className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                onChange={(event) => setTeamSlug(event.target.value)}
                value={teamSlug}
              >
                <option value="">{t(locale, { ru: "Выбери опубликованную команду", en: "Select a published team" })}</option>
                {teams.map((team) => (
                  <option key={team.id} value={team.slug}>
                    {team.title} ({team.slug})
                  </option>
                ))}
              </select>
            </label>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                GitHub owner
                <input
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  onChange={(event) => setRepoOwner(event.target.value)}
                  placeholder="stemirkhan"
                  type="text"
                  value={repoOwner}
                />
              </label>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                GitHub repo
                <input
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  onChange={(event) => setRepoName(event.target.value)}
                  placeholder="team-agent-platform"
                  type="text"
                  value={repoName}
                />
              </label>
            </div>

            <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
              {t(locale, { ru: "Базовая ветка (опционально)", en: "Base branch (optional)" })}
              <input
                className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                onChange={(event) => setBaseBranch(event.target.value)}
                placeholder={selectedRepo?.default_branch ?? "main"}
                type="text"
                value={baseBranch}
              />
            </label>

            {suggestedRepos.length > 0 ? (
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Быстрый выбор репозитория", en: "Quick repo selection" })}
                </p>
                <div className="flex flex-wrap gap-2">
                  {suggestedRepos.slice(0, 8).map((repo) => {
                    const active = repo.owner === repoOwner && repo.name === repoName;
                    return (
                      <button
                        className={[
                          "rounded-full px-3 py-1.5 text-xs font-semibold transition",
                          active
                            ? "bg-brand-100 text-brand-800 ring-1 ring-brand-300 dark:bg-zinc-800 dark:text-slate-100 dark:ring-zinc-600"
                            : "bg-white text-slate-700 ring-1 ring-slate-300 hover:bg-slate-100 dark:bg-zinc-950 dark:text-slate-200 dark:ring-zinc-700 dark:hover:bg-zinc-800"
                        ].join(" ")}
                        key={repo.full_name}
                        onClick={() => {
                          setRepoOwner(repo.owner);
                          setRepoName(repo.name);
                          setBaseBranch(repo.default_branch ?? "");
                        }}
                        type="button"
                      >
                        {repo.full_name}
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null}
          </div>

          <div className="space-y-5 rounded-2xl border border-slate-200 bg-slate-50/70 p-4 dark:border-zinc-800 dark:bg-zinc-900/70">
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "Задача и параметры Codex", en: "Task and Codex parameters" })}
              </h3>
            </div>

            <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
              {t(locale, { ru: "Issue number (опционально)", en: "Issue number (optional)" })}
              <input
                className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                onChange={(event) => setIssueNumber(event.target.value)}
                placeholder="12848"
                type="number"
                value={issueNumber}
              />
            </label>

            <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
              {t(locale, { ru: "Заголовок run (опционально)", en: "Run title (optional)" })}
              <input
                className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                onChange={(event) => setTitle(event.target.value)}
                placeholder={t(locale, { ru: "Например: Fix export terminal flow", en: "For example: Fix export terminal flow" })}
                type="text"
                value={title}
              />
            </label>

            <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
              {t(locale, { ru: "Краткая цель (опционально)", en: "Short goal summary (optional)" })}
              <textarea
                className="mt-1 min-h-24 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                onChange={(event) => setSummary(event.target.value)}
                placeholder={t(locale, {
                  ru: "Что должно получиться в итоге и какие ограничения важны.",
                  en: "What should be true at the end and which constraints matter."
                })}
                value={summary}
              />
            </label>

            <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
              {t(locale, { ru: "Ручное описание задачи", en: "Manual task description" })}
              <textarea
                className="mt-1 min-h-32 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                onChange={(event) => setTaskText(event.target.value)}
                placeholder={t(locale, {
                  ru: "Если issue не указан, опиши задачу здесь. TASK.md будет собран из этих данных.",
                  en: "If no issue is selected, describe the task here. TASK.md will be composed from these inputs."
                })}
                value={taskText}
              />
            </label>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200 md:col-span-2">
                Codex model
                <input
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  onChange={(event) => setCodexModel(event.target.value)}
                  placeholder={t(locale, {
                    ru: "Оставь пустым для модели аккаунта",
                    en: "Leave empty to use the account default"
                  })}
                  type="text"
                  value={codexModel}
                />
                <span className="mt-1 block text-xs font-normal text-slate-500 dark:text-slate-400">
                  {t(locale, {
                    ru: "При browser-login Codex лучше не форсировать model без явной необходимости.",
                    en: "With browser-login Codex it is better not to force a model unless you need one explicitly."
                  })}
                </span>
              </label>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t(locale, { ru: "Reasoning effort", en: "Reasoning effort" })}
                <select
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  onChange={(event) => setReasoningEffort(event.target.value as CodexReasoningEffort)}
                  value={reasoningEffort}
                >
                  <option value="low">low</option>
                  <option value="medium">medium</option>
                  <option value="high">high</option>
                </select>
              </label>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                Sandbox mode
                <select
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  onChange={(event) => setSandboxMode(event.target.value as CodexSandboxMode)}
                  value={sandboxMode}
                >
                  <option value="read-only">read-only</option>
                  <option value="workspace-write">workspace-write</option>
                  <option value="danger-full-access">danger-full-access</option>
                </select>
              </label>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/70">
          <div className="text-sm text-slate-600 dark:text-slate-300">
            {user ? (
              <span>
                {t(locale, { ru: "Запуск будет создан от имени", en: "Run will be created as" })} <strong>{user.display_name}</strong>
              </span>
            ) : (
              <span>{t(locale, { ru: "Нужна авторизация в платформе", en: "Platform sign-in is required" })}</span>
            )}
          </div>
          <Button
            disabled={
              submitting ||
              loadingUser ||
              !user ||
              teams.length === 0 ||
              readiness?.effective_ready === false
            }
            type="submit"
          >
            {submitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t(locale, { ru: "Создание run...", en: "Creating run..." })}
              </>
            ) : (
              <>
                <Play className="mr-2 h-4 w-4" />
                {t(locale, { ru: "Запустить команду", en: "Run team" })}
              </>
            )}
          </Button>
        </div>
      </form>
    </section>
  );
}
