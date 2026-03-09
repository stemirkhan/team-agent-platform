"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  FolderGit2,
  Loader2,
  Play,
  Settings2,
  ShieldCheck,
  Sparkles,
  UserRound
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
  createRun,
  fetchGitHubIssue,
  fetchGitHubRepo,
  fetchGitHubRepoBranches,
  fetchGitHubRepoIssues,
  fetchGitHubRepos,
  type CodexReasoningEffort,
  type CodexSandboxMode,
  type GitHubBranch,
  type GitHubIssue,
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

function parseRepositoryInput(value: string): { owner: string; name: string } | null {
  const normalized = value.trim().replace(/^https?:\/\/github\.com\//, "").replace(/\.git$/, "");
  const segments = normalized.split("/").filter(Boolean);
  if (segments.length !== 2) {
    return null;
  }

  return { owner: segments[0], name: segments[1] };
}

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

function dedupeRepos(repos: GitHubRepo[]): GitHubRepo[] {
  const seen = new Set<string>();
  return repos.filter((repo) => {
    if (seen.has(repo.full_name)) {
      return false;
    }
    seen.add(repo.full_name);
    return true;
  });
}

const CODEX_MODEL_OPTIONS = [
  "gpt-5.3-codex",
  "gpt-5.2-codex",
  "gpt-5.1-codex",
  "gpt-5.1-codex-max",
  "gpt-5-codex",
  "gpt-5.1-codex-mini",
] as const;

type CodexModelOption = (typeof CODEX_MODEL_OPTIONS)[number];

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
  const [repository, setRepository] = useState(
    initialOwner && initialRepo
      ? `${initialOwner}/${initialRepo}`
      : suggestedRepos[0]?.full_name ?? ""
  );
  const [repoSearch, setRepoSearch] = useState("");
  const [repoOptions, setRepoOptions] = useState<GitHubRepo[]>(suggestedRepos);
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [repoSearchError, setRepoSearchError] = useState<string | null>(null);
  const [selectedRepoFallback, setSelectedRepoFallback] = useState<GitHubRepo | null>(null);
  const [baseBranch, setBaseBranch] = useState("");
  const [branchOptions, setBranchOptions] = useState<GitHubBranch[]>([]);
  const [loadingBranches, setLoadingBranches] = useState(false);
  const [branchError, setBranchError] = useState<string | null>(null);
  const [issueSearch, setIssueSearch] = useState("");
  const [issueOptions, setIssueOptions] = useState<GitHubIssue[]>([]);
  const [loadingIssues, setLoadingIssues] = useState(false);
  const [issueError, setIssueError] = useState<string | null>(null);
  const [selectedIssueFallback, setSelectedIssueFallback] = useState<GitHubIssue | null>(null);
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

  const parsedRepository = useMemo(() => parseRepositoryInput(repository), [repository]);
  const selectedRepoFromOptions = useMemo(
    () =>
      dedupeRepos([...repoOptions, ...suggestedRepos]).find(
        (repo) =>
          repo.owner === parsedRepository?.owner && repo.name === parsedRepository?.name
      ) ?? null,
    [parsedRepository, repoOptions, suggestedRepos]
  );
  const selectedRepo = selectedRepoFromOptions ?? selectedRepoFallback;
  const selectedTeam = useMemo(
    () => teams.find((team) => team.slug === teamSlug) ?? null,
    [teamSlug, teams]
  );
  const selectedIssueFromOptions = useMemo(
    () => issueOptions.find((issue) => issue.number === parseIssueNumber(issueNumber)) ?? null,
    [issueNumber, issueOptions]
  );
  const selectedIssue = selectedIssueFromOptions ?? selectedIssueFallback;
  const displayedRepoOptions = useMemo(() => {
    const options = repoSearch.trim()
      ? repoOptions
      : dedupeRepos([...suggestedRepos, ...repoOptions]);
    return options.slice(0, 8);
  }, [repoOptions, repoSearch, suggestedRepos]);
  const selectedCodexModelOption = useMemo(() => {
    if (!codexModel.trim()) {
      return "account-default";
    }

    return (CODEX_MODEL_OPTIONS as readonly string[]).includes(codexModel)
      ? codexModel
      : "custom";
  }, [codexModel]);
  const usingIssueFlow = issueNumber.trim().length > 0;
  const hasManualTask = taskText.trim().length > 0;
  const hasTaskSource = usingIssueFlow || hasManualTask;
  const codexOverridesSelected =
    codexModel.trim().length > 0 ||
    reasoningEffort !== "medium" ||
    sandboxMode !== "workspace-write";

  useEffect(() => {
    let cancelled = false;
    const query = repoSearch.trim();

    if (!query) {
      setRepoOptions(suggestedRepos);
      setRepoSearchError(null);
      setLoadingRepos(false);
      return;
    }

    const timeoutId = setTimeout(async () => {
      if (!cancelled) {
        setLoadingRepos(true);
        setRepoSearchError(null);
      }

      try {
        const response = await fetchGitHubRepos({ q: query, limit: 12 });
        if (!cancelled) {
          setRepoOptions(response.items);
        }
      } catch (error) {
        if (!cancelled) {
          setRepoOptions([]);
          setRepoSearchError(
            error instanceof Error
              ? error.message
              : t(locale, {
                  ru: "Не удалось выполнить поиск репозиториев.",
                  en: "Failed to search repositories."
                })
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingRepos(false);
        }
      }
    }, 250);

    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [locale, repoSearch, suggestedRepos]);

  useEffect(() => {
    let cancelled = false;

    async function resolveSelectedRepo() {
      if (!parsedRepository) {
        if (!cancelled) {
          setSelectedRepoFallback(null);
        }
        return;
      }

      if (selectedRepoFromOptions) {
        if (!cancelled) {
          setSelectedRepoFallback(null);
        }
        return;
      }

      try {
        const repo = await fetchGitHubRepo(parsedRepository.owner, parsedRepository.name);
        if (!cancelled) {
          setSelectedRepoFallback(repo);
        }
      } catch {
        if (!cancelled) {
          setSelectedRepoFallback(null);
        }
      }
    }

    void resolveSelectedRepo();

    return () => {
      cancelled = true;
    };
  }, [parsedRepository, selectedRepoFromOptions]);

  useEffect(() => {
    let cancelled = false;

    async function loadBranches() {
      if (!parsedRepository) {
        if (!cancelled) {
          setBranchOptions([]);
          setBranchError(null);
          setLoadingBranches(false);
        }
        return;
      }

      if (!cancelled) {
        setLoadingBranches(true);
        setBranchError(null);
      }

      try {
        const response = await fetchGitHubRepoBranches(parsedRepository.owner, parsedRepository.name, 30);
        if (!cancelled) {
          setBranchOptions(response.items);
        }
      } catch (error) {
        if (!cancelled) {
          setBranchOptions([]);
          setBranchError(
            error instanceof Error
              ? error.message
              : t(locale, {
                  ru: "Не удалось загрузить ветки репозитория.",
                  en: "Failed to load repository branches."
                })
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingBranches(false);
        }
      }
    }

    void loadBranches();

    return () => {
      cancelled = true;
    };
  }, [locale, parsedRepository]);

  useEffect(() => {
    let cancelled = false;
    const query = issueSearch.trim();

    async function loadIssues() {
      if (!parsedRepository || selectedRepo?.has_issues_enabled === false) {
        if (!cancelled) {
          setIssueOptions([]);
          setIssueError(null);
          setLoadingIssues(false);
        }
        return;
      }

      if (!cancelled) {
        setLoadingIssues(true);
        setIssueError(null);
      }

      try {
        const response = await fetchGitHubRepoIssues(parsedRepository.owner, parsedRepository.name, {
          state: query ? "all" : "open",
          limit: query ? 20 : 12,
          q: query || undefined
        });
        if (!cancelled) {
          setIssueOptions(response.items);
        }
      } catch (error) {
        if (!cancelled) {
          setIssueOptions([]);
          setIssueError(
            error instanceof Error
              ? error.message
              : t(locale, {
                  ru: "Не удалось загрузить issue репозитория.",
                  en: "Failed to load repository issues."
                })
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingIssues(false);
        }
      }
    }

    const timeoutId = setTimeout(() => {
      void loadIssues();
    }, query ? 250 : 0);

    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [issueSearch, locale, parsedRepository, selectedRepo]);

  useEffect(() => {
    let cancelled = false;
    const number = parseIssueNumber(issueNumber);

    async function resolveSelectedIssue() {
      if (!parsedRepository || !number) {
        if (!cancelled) {
          setSelectedIssueFallback(null);
        }
        return;
      }

      if (selectedIssueFromOptions?.number === number) {
        if (!cancelled) {
          setSelectedIssueFallback(null);
        }
        return;
      }

      try {
        const issue = await fetchGitHubIssue(parsedRepository.owner, parsedRepository.name, number);
        if (!cancelled) {
          setSelectedIssueFallback(issue);
        }
      } catch {
        if (!cancelled) {
          setSelectedIssueFallback(null);
        }
      }
    }

    void resolveSelectedIssue();

    return () => {
      cancelled = true;
    };
  }, [issueNumber, parsedRepository, selectedIssueFromOptions]);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!token) {
      router.push("/auth/login");
      return;
    }

    if (!teamSlug || !parsedRepository) {
      setErrorMessage(
        t(locale, {
          ru: "Выбери команду и репозиторий перед запуском.",
          en: "Select a team and repository before starting the run."
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
          repo_owner: parsedRepository.owner,
          repo_name: parsedRepository.name,
          base_branch: baseBranch.trim() || undefined,
          issue_number: parseIssueNumber(issueNumber),
          task_text: taskText.trim() || undefined,
          title: usingIssueFlow ? undefined : title.trim() || undefined,
          summary: usingIssueFlow ? undefined : summary.trim() || undefined,
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
      <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 dark:border-zinc-800 dark:bg-zinc-900/70">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "Как пройдет запуск", en: "Launch flow" })}
              </p>
              <p className="mt-1 max-w-3xl text-sm text-slate-600 dark:text-slate-300">
                {t(locale, {
                  ru: "Собери контекст задачи, а платформа подготовит workspace, стартует Codex и доведет результат до ветки и draft PR.",
                  en: "Provide the task context and the platform will prepare the workspace, start Codex, and carry the result through to a branch and draft PR."
                })}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {[
                t(locale, { ru: "Команда и repo", en: "Team and repo" }),
                t(locale, { ru: "Контекст задачи", en: "Task context" }),
                t(locale, { ru: "Codex run", en: "Codex run" }),
                t(locale, { ru: "Branch + draft PR", en: "Branch + draft PR" })
              ].map((step) => (
                <span
                  className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-600 ring-1 ring-slate-200 dark:bg-zinc-950 dark:text-slate-300 dark:ring-zinc-700"
                  key={step}
                >
                  {step}
                </span>
              ))}
            </div>
          </div>
          <Link
            className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-200 dark:bg-zinc-950 dark:text-slate-200 dark:hover:bg-zinc-800"
            href="/diagnostics"
          >
            <Sparkles className="h-3.5 w-3.5" />
            {t(locale, { ru: "Открыть диагностику", en: "Open diagnostics" })}
          </Link>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <span
            className={[
              "inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold",
              readiness?.effective_ready === false
                ? "bg-rose-100 text-rose-700 dark:bg-rose-500/10 dark:text-rose-200"
                : "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-200"
            ].join(" ")}
          >
            <ShieldCheck className="h-3.5 w-3.5" />
            {readiness?.effective_ready === false
              ? t(locale, { ru: "Нужна диагностика", en: "Diagnostics required" })
              : t(locale, { ru: "Host execution готов", en: "Host execution ready" })}
          </span>
          {user ? (
            <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-950 dark:text-slate-200 dark:ring-zinc-700">
              <UserRound className="h-3.5 w-3.5" />
              {user.display_name}
            </span>
          ) : null}
          {parsedRepository ? (
            <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-950 dark:text-slate-200 dark:ring-zinc-700">
              <FolderGit2 className="h-3.5 w-3.5" />
              {parsedRepository.owner}/{parsedRepository.name}
            </span>
          ) : null}
          <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-950 dark:text-slate-200 dark:ring-zinc-700">
            <FileText className="h-3.5 w-3.5" />
            {usingIssueFlow
              ? t(locale, { ru: "Issue-driven flow", en: "Issue-driven flow" })
              : t(locale, { ru: "Manual task flow", en: "Manual task flow" })}
          </span>
        </div>
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
                {t(locale, { ru: "Контекст запуска", en: "Launch context" })}
              </h3>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                {t(locale, {
                  ru: "Выбери опубликованную команду и target repo, над которым будет работать Codex.",
                  en: "Choose the published team and target repo that Codex should work on."
                })}
              </p>
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

            {selectedTeam?.description ? (
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 dark:border-zinc-800 dark:bg-zinc-950 dark:text-slate-300">
                {selectedTeam.description}
              </div>
            ) : null}

            <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
              {t(locale, { ru: "Поиск репозитория", en: "Search repository" })}
              <input
                className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                onChange={(event) => setRepoSearch(event.target.value)}
                placeholder="stemirkhan/team-agent-platform"
                type="text"
                value={repoSearch}
              />
            </label>

            {loadingRepos ? (
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "Ищу репозитории...", en: "Searching repositories..." })}
              </p>
            ) : null}

            {repoSearchError ? (
              <p className="text-xs text-rose-600 dark:text-rose-300">{repoSearchError}</p>
            ) : null}

            {parsedRepository ? (
              <div className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                      {t(locale, { ru: "Выбранный repo", en: "Selected repo" })}
                    </p>
                    <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-slate-100">
                      {selectedRepo?.full_name ?? `${parsedRepository.owner}/${parsedRepository.name}`}
                    </p>
                  </div>
                  {selectedRepo ? (
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700 dark:bg-zinc-800 dark:text-slate-200">
                      {selectedRepo.is_private
                        ? t(locale, { ru: "private", en: "private" })
                        : t(locale, { ru: "public", en: "public" })}
                    </span>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400">
                  <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1 dark:bg-zinc-800">
                    <Sparkles className="h-3 w-3" />
                    {t(locale, { ru: "default branch", en: "default branch" })}:{" "}
                    <strong className="text-slate-700 dark:text-slate-200">
                      {selectedRepo?.default_branch ?? "main"}
                    </strong>
                  </span>
                  {selectedRepo ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1 dark:bg-zinc-800">
                      <CheckCircle2 className="h-3 w-3" />
                      {selectedRepo.has_issues_enabled
                        ? t(locale, { ru: "issues включены", en: "issues enabled" })
                        : t(locale, { ru: "issues выключены", en: "issues disabled" })}
                    </span>
                  ) : null}
                </div>
              </div>
            ) : null}

            <details className="rounded-2xl border border-slate-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
              <summary className="cursor-pointer list-none px-4 py-3 text-sm font-semibold text-slate-800 marker:hidden dark:text-slate-100">
                {t(locale, { ru: "Изменить базовую ветку", en: "Change base branch" })}
              </summary>
              <div className="border-t border-slate-200 px-4 py-4 dark:border-zinc-800">
                <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                  {t(locale, { ru: "Базовая ветка (опционально)", en: "Base branch (optional)" })}
                  <input
                    className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                    list="repo-branches"
                    onChange={(event) => setBaseBranch(event.target.value)}
                    placeholder={selectedRepo?.default_branch ?? "main"}
                    type="text"
                    value={baseBranch}
                  />
                  <datalist id="repo-branches">
                    {branchOptions.map((branch) => (
                      <option key={branch.name} value={branch.name} />
                    ))}
                  </datalist>
                  <span className="mt-1 block text-xs font-normal text-slate-500 dark:text-slate-400">
                    {t(locale, {
                      ru: "Оставь пустым, чтобы использовать default branch выбранного repo.",
                      en: "Leave empty to use the selected repo default branch."
                    })}
                  </span>
                </label>

                {loadingBranches ? (
                  <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                    {t(locale, { ru: "Загружаю доступные ветки...", en: "Loading available branches..." })}
                  </p>
                ) : null}

                {branchError ? (
                  <p className="mt-3 text-xs text-rose-600 dark:text-rose-300">{branchError}</p>
                ) : null}

                {!loadingBranches && branchOptions.length > 0 ? (
                  <div className="mt-3 space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
                      {t(locale, { ru: "Доступные ветки", en: "Available branches" })}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {branchOptions.slice(0, 8).map((branch) => (
                        <button
                          className={[
                            "rounded-full px-3 py-1 text-xs font-semibold transition",
                            baseBranch === branch.name
                              ? "bg-brand-100 text-brand-800 ring-1 ring-brand-300 dark:bg-zinc-800 dark:text-slate-100 dark:ring-zinc-600"
                              : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-zinc-900 dark:text-slate-200 dark:hover:bg-zinc-800"
                          ].join(" ")}
                          key={branch.name}
                          onClick={() => setBaseBranch(branch.name)}
                          type="button"
                        >
                          {branch.name}
                          {branch.is_default ? " • default" : ""}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </details>

            {displayedRepoOptions.length > 0 ? (
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                  {repoSearch.trim()
                    ? t(locale, { ru: "Результаты поиска", en: "Search results" })
                    : t(locale, { ru: "Доступные репозитории", en: "Available repositories" })}
                </p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {displayedRepoOptions.map((repo) => {
                    const active = repo.full_name === parsedRepository?.owner + "/" + parsedRepository?.name;
                    return (
                      <button
                        className={[
                          "rounded-2xl border px-3 py-3 text-left transition",
                          active
                            ? "border-brand-300 bg-brand-50 text-brand-900 shadow-sm dark:border-brand-500/40 dark:bg-zinc-950 dark:text-slate-100"
                            : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-100 dark:border-zinc-800 dark:bg-zinc-950 dark:text-slate-200 dark:hover:bg-zinc-800"
                        ].join(" ")}
                        key={repo.full_name}
                        onClick={() => {
                          setRepository(repo.full_name);
                          setRepoSearch("");
                          setSelectedRepoFallback(repo);
                          setBaseBranch("");
                          setIssueNumber("");
                          setIssueSearch("");
                          setSelectedIssueFallback(null);
                        }}
                        type="button"
                      >
                        <div className="text-sm font-semibold">{repo.full_name}</div>
                        <div className="mt-2 flex flex-wrap gap-2 text-[11px] font-medium uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
                          <span>{repo.default_branch ?? "main"}</span>
                          <span>{repo.is_private ? "private" : "public"}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null}

            {!loadingRepos && !repoSearchError && repoSearch.trim() && displayedRepoOptions.length === 0 ? (
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {t(locale, {
                  ru: "По этому запросу репозитории не нашлись.",
                  en: "No repositories matched this search."
                })}
              </p>
            ) : null}
          </div>

          <div className="space-y-5 rounded-2xl border border-slate-200 bg-slate-50/70 p-4 dark:border-zinc-800 dark:bg-zinc-900/70">
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "Задача и ожидаемый результат", en: "Task and expected result" })}
              </h3>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                {t(locale, {
                  ru: "Можно запустить команду по issue или собрать TASK.md из ручного описания.",
                  en: "You can launch the team from an issue or compose TASK.md from manual instructions."
                })}
              </p>
            </div>

            <div
              className={[
                "rounded-2xl border px-4 py-3 text-sm",
                hasTaskSource
                  ? "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-200"
                  : "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200"
              ].join(" ")}
            >
              <div className="flex items-start gap-3">
                {hasTaskSource ? (
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                ) : (
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                )}
                <div>
                  <p className="font-semibold">
                    {usingIssueFlow
                      ? t(locale, { ru: "Issue станет главным task context.", en: "The issue will be the primary task context." })
                      : hasManualTask
                        ? t(locale, { ru: "Run будет собран из ручного описания задачи.", en: "The run will be composed from your manual task description." })
                        : t(locale, { ru: "Нужен issue number или ручное описание задачи.", en: "You need an issue number or a manual task description." })}
                  </p>
                  <p className="mt-1 opacity-90">
                    {usingIssueFlow
                      ? t(locale, {
                          ru: "Текст ниже можно использовать как дополнительные инструкции и ограничения для Codex.",
                          en: "You can use the text below for additional Codex instructions and constraints."
                        })
                      : t(locale, {
                          ru: "Если issue нет, опиши цель, ограничения и ожидаемый результат вручную.",
                          en: "If there is no issue, describe the goal, constraints, and expected outcome manually."
                        })}
                  </p>
                </div>
              </div>
            </div>

            {selectedRepo?.has_issues_enabled === false ? (
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 dark:border-zinc-800 dark:bg-zinc-950 dark:text-slate-300">
                {t(locale, {
                  ru: "У выбранного репозитория GitHub Issues выключены. Можно оставить поле issue пустым и описать задачу вручную.",
                  en: "GitHub Issues are disabled for the selected repository. Leave the issue field empty and describe the task manually."
                })}
              </div>
            ) : null}

            {parsedRepository && selectedRepo?.has_issues_enabled !== false ? (
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t(locale, { ru: "Поиск issue", en: "Search issue" })}
                <input
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  onChange={(event) => setIssueSearch(event.target.value)}
                  placeholder={t(locale, {
                    ru: "Например: terminal, hydration или #12848",
                    en: "For example: terminal, hydration, or #12848"
                  })}
                  type="text"
                  value={issueSearch}
                />
              </label>
            ) : null}

            {loadingIssues ? (
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {issueSearch.trim()
                  ? t(locale, { ru: "Ищу issue...", en: "Searching issues..." })
                  : t(locale, { ru: "Загружаю open issue выбранного репозитория...", en: "Loading open issues for the selected repository..." })}
              </p>
            ) : null}

            {issueError ? (
              <p className="text-xs text-rose-600 dark:text-rose-300">{issueError}</p>
            ) : null}

            {!loadingIssues && issueOptions.length > 0 ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
                    {issueSearch.trim()
                      ? t(locale, { ru: "Результаты поиска issue", en: "Issue search results" })
                      : t(locale, { ru: "Open issue этого repo", en: "Open issues for this repo" })}
                  </p>
                  {usingIssueFlow ? (
                    <button
                      className="text-xs font-semibold text-slate-500 transition hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                      onClick={() => {
                        setIssueNumber("");
                        setSelectedIssueFallback(null);
                      }}
                      type="button"
                    >
                      {t(locale, { ru: "Очистить issue", en: "Clear issue" })}
                    </button>
                  ) : (
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                      {t(locale, {
                        ru: "Нажми, чтобы выбрать issue",
                        en: "Click to select an issue"
                      })}
                    </span>
                  )}
                </div>
                <div className="grid gap-2">
                  {issueOptions.slice(0, 6).map((issue) => {
                    const active = selectedIssue?.number === issue.number;
                    return (
                      <button
                        className={[
                          "rounded-2xl border px-3 py-3 text-left transition",
                          active
                            ? "border-brand-300 bg-brand-50 text-brand-900 shadow-sm dark:border-brand-500/40 dark:bg-zinc-950 dark:text-slate-100"
                            : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-100 dark:border-zinc-800 dark:bg-zinc-950 dark:text-slate-200 dark:hover:bg-zinc-800"
                        ].join(" ")}
                        key={issue.number}
                        onClick={() => {
                          setIssueNumber(String(issue.number));
                          setSelectedIssueFallback(issue);
                          if (!title.trim()) {
                            setTitle(issue.title);
                          }
                        }}
                        type="button"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="text-sm font-semibold">
                              #{issue.number} {issue.title}
                            </div>
                            <div className="mt-1 flex flex-wrap gap-2 text-[11px] font-medium uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
                              {issue.author_login ? <span>@{issue.author_login}</span> : null}
                              <span>{issue.comments_count} comments</span>
                              {issue.labels.slice(0, 2).map((label) => (
                                <span key={label}>{label}</span>
                              ))}
                            </div>
                          </div>
                          {active ? (
                            <span className="rounded-full bg-brand-100 px-2 py-1 text-[11px] font-semibold text-brand-800 dark:bg-zinc-800 dark:text-slate-100">
                              {t(locale, { ru: "выбрано", en: "selected" })}
                            </span>
                          ) : null}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null}

            {selectedIssue ? (
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 dark:border-zinc-800 dark:bg-zinc-950 dark:text-slate-200">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">#{selectedIssue.number}</span>
                    <span className="font-semibold">{selectedIssue.title}</span>
                  </div>
                  <button
                    className="text-xs font-semibold text-slate-500 transition hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                    onClick={() => {
                      setIssueNumber("");
                      setSelectedIssueFallback(null);
                    }}
                    type="button"
                  >
                    {t(locale, { ru: "Очистить issue", en: "Clear issue" })}
                  </button>
                </div>
                <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400">
                  {selectedIssue.author_login ? <span>@{selectedIssue.author_login}</span> : null}
                  <span>{selectedIssue.comments_count} comments</span>
                  {selectedIssue.labels.map((label) => (
                    <span
                      className="rounded-full bg-slate-100 px-2 py-0.5 dark:bg-zinc-800"
                      key={label}
                    >
                      {label}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            {usingIssueFlow && !selectedIssue ? (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 dark:border-zinc-800 dark:bg-zinc-950 dark:text-slate-200">
                <div className="font-semibold">
                  {t(locale, { ru: "Выбрана issue", en: "Selected issue" })} #{issueNumber}
                </div>
                <button
                  className="text-xs font-semibold text-slate-500 transition hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                  onClick={() => {
                    setIssueNumber("");
                    setSelectedIssueFallback(null);
                  }}
                  type="button"
                >
                  {t(locale, { ru: "Очистить issue", en: "Clear issue" })}
                </button>
              </div>
            ) : null}

            {!loadingIssues &&
            !issueError &&
            parsedRepository &&
            selectedRepo?.has_issues_enabled !== false &&
            issueOptions.length === 0 ? (
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {issueSearch.trim()
                  ? t(locale, {
                      ru: "По этому запросу issue не нашлись. Попробуй другой запрос или опиши задачу текстом.",
                      en: "No issues matched this search. Try another query or describe the task in text."
                    })
                  : t(locale, {
                      ru: "Для этого репозитория не нашлось открытых issue. Можно описать задачу текстом.",
                      en: "No open issues were found for this repository. You can describe the task in text."
                    })}
              </p>
            ) : null}

            <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
              {t(locale, { ru: "Заголовок run (опционально)", en: "Run title (optional)" })}
              <input
                className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-950"
                disabled={usingIssueFlow}
                onChange={(event) => setTitle(event.target.value)}
                placeholder={t(locale, { ru: "Например: Fix export terminal flow", en: "For example: Fix export terminal flow" })}
                type="text"
                value={title}
              />
            </label>

            <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
              {t(locale, { ru: "Краткая цель (опционально)", en: "Short goal summary (optional)" })}
              <textarea
                className="mt-1 min-h-24 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-950"
                disabled={usingIssueFlow}
                onChange={(event) => setSummary(event.target.value)}
                placeholder={t(locale, {
                  ru: "Что должно получиться в итоге и какие ограничения важны.",
                  en: "What should be true at the end and which constraints matter."
                })}
                value={summary}
              />
            </label>

            <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
              {usingIssueFlow
                ? t(locale, {
                    ru: "Дополнительные инструкции для Codex (опционально)",
                    en: "Extra instructions for Codex (optional)"
                  })
                : t(locale, { ru: "Описание задачи", en: "Task description" })}
              <textarea
                className="mt-1 min-h-32 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                onChange={(event) => setTaskText(event.target.value)}
                placeholder={
                  usingIssueFlow
                    ? t(locale, {
                        ru: "Например: не трогай onboarding, сохрани существующие маршруты, проверь mobile layout.",
                        en: "For example: do not touch onboarding, keep existing routes, verify the mobile layout."
                      })
                    : t(locale, {
                        ru: "Опиши задачу, ограничения и желаемый итог. TASK.md будет собран из этих данных.",
                        en: "Describe the task, constraints, and desired outcome. TASK.md will be composed from these inputs."
                      })
                }
                value={taskText}
              />
              <span className="mt-1 block text-xs font-normal text-slate-500 dark:text-slate-400">
                {usingIssueFlow
                  ? t(locale, {
                      ru: "Если поле пустое, run будет в основном опираться на issue context.",
                      en: "If you leave this empty, the run will mainly rely on the issue context."
                    })
                  : t(locale, {
                      ru: "Это главное поле, если запуск не привязан к issue.",
                      en: "This is the main field when the launch is not tied to an issue."
                    })}
              </span>
            </label>
          </div>
        </div>

        <details className="rounded-2xl border border-slate-200 bg-slate-50/70 dark:border-zinc-800 dark:bg-zinc-900/70">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 marker:hidden">
            <span className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100">
              <Settings2 className="h-4 w-4" />
              {t(locale, { ru: "Параметры Codex и sandbox", en: "Codex and sandbox settings" })}
            </span>
            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
              {codexOverridesSelected
                ? t(locale, { ru: "Есть overrides", en: "Custom overrides" })
                : t(locale, { ru: "Обычно можно не менять", en: "Defaults are usually enough" })}
            </span>
          </summary>
          <div className="grid gap-4 border-t border-slate-200 px-4 py-4 dark:border-zinc-800 md:grid-cols-2">
            <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200 md:col-span-2">
              Codex model
              <select
                className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                onChange={(event) => {
                  const nextValue = event.target.value;
                  if (nextValue === "account-default") {
                    setCodexModel("");
                    return;
                  }
                  if (nextValue === "custom") {
                    setCodexModel(
                      (CODEX_MODEL_OPTIONS as readonly string[]).includes(codexModel)
                        ? ""
                        : codexModel
                    );
                    return;
                  }
                  setCodexModel(nextValue as CodexModelOption);
                }}
                value={selectedCodexModelOption}
              >
                <option value="account-default">
                  {t(locale, {
                    ru: "Модель аккаунта по умолчанию",
                    en: "Account default model"
                  })}
                </option>
                {CODEX_MODEL_OPTIONS.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
                <option value="custom">
                  {t(locale, { ru: "Custom model...", en: "Custom model..." })}
                </option>
              </select>
              <span className="mt-1 block text-xs font-normal text-slate-500 dark:text-slate-400">
                {t(locale, {
                  ru: "При browser-login Codex лучше не форсировать model без явной необходимости.",
                  en: "With browser-login Codex it is better not to force a model unless you need one explicitly."
                })}
              </span>
            </label>
            {selectedCodexModelOption === "custom" ? (
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200 md:col-span-2">
                {t(locale, { ru: "Custom model id", en: "Custom model id" })}
                <input
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  onChange={(event) => setCodexModel(event.target.value)}
                  placeholder="gpt-5.3-codex-spark"
                  type="text"
                  value={codexModel}
                />
              </label>
            ) : null}
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
                <option value="xhigh">xhigh</option>
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
        </details>

        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/70">
          <div className="space-y-2">
            <div className="text-sm text-slate-600 dark:text-slate-300">
              {user ? (
                <span>
                  {t(locale, { ru: "Запуск будет создан от имени", en: "Run will be created as" })} <strong>{user.display_name}</strong>
                </span>
              ) : (
                <span>{t(locale, { ru: "Нужна авторизация в платформе", en: "Platform sign-in is required" })}</span>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {selectedTeam ? (
                <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-950 dark:text-slate-200 dark:ring-zinc-700">
                  {selectedTeam.title}
                </span>
              ) : null}
              {parsedRepository ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-950 dark:text-slate-200 dark:ring-zinc-700">
                  <FolderGit2 className="h-3 w-3" />
                  {parsedRepository.owner}/{parsedRepository.name}
                </span>
              ) : null}
              <span className="inline-flex items-center gap-1 rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-950 dark:text-slate-200 dark:ring-zinc-700">
                <FileText className="h-3 w-3" />
                {usingIssueFlow
                  ? t(locale, { ru: "Issue context", en: "Issue context" })
                  : t(locale, { ru: "Manual task", en: "Manual task" })}
              </span>
            </div>
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
