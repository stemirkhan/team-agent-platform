import Link from "next/link";
import {
  ArrowLeft,
  ExternalLink,
  FolderGit2,
  GitBranch,
  GitPullRequest,
  MessageSquareText,
  PlaySquare
} from "lucide-react";

import { ExecutionPageContainer } from "@/components/layout/execution-page-container";
import {
  fetchGitHubRepo,
  fetchGitHubRepoIssues,
  fetchGitHubRepoPulls
} from "@/lib/api";
import { t } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n.server";

function normalizeIssueState(value: string | string[] | undefined): "open" | "closed" | "all" {
  const normalized = Array.isArray(value) ? value[0] : value;
  if (normalized === "closed" || normalized === "all") {
    return normalized;
  }
  return "open";
}

function normalizePullState(
  value: string | string[] | undefined
): "open" | "closed" | "merged" | "all" {
  const normalized = Array.isArray(value) ? value[0] : value;
  if (normalized === "closed" || normalized === "merged" || normalized === "all") {
    return normalized;
  }
  return "open";
}

function buildRepoHref(
  owner: string,
  repo: string,
  issueState: "open" | "closed" | "all",
  pullState: "open" | "closed" | "merged" | "all"
): string {
  const params = new URLSearchParams();
  params.set("issueState", issueState);
  params.set("pullState", pullState);
  return `/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}?${params.toString()}`;
}

export default async function RepoDetailsPage({
  params,
  searchParams
}: {
  params: { owner: string; repo: string };
  searchParams?: { issueState?: string | string[]; pullState?: string | string[] };
}) {
  const locale = getRequestLocale();
  const issueState = normalizeIssueState(searchParams?.issueState);
  const pullState = normalizePullState(searchParams?.pullState);

  let repo = null;
  let issues = null;
  let pulls = null;
  let repoError: string | null = null;
  let issuesError: string | null = null;
  let pullsError: string | null = null;

  try {
    repo = await fetchGitHubRepo(params.owner, params.repo);
  } catch (error) {
    repoError =
      error instanceof Error
        ? error.message
        : t(locale, {
            ru: "Не удалось загрузить репозиторий.",
            en: "Failed to load repository."
          });
  }

  if (repo) {
    const [issuesResult, pullsResult] = await Promise.allSettled([
      fetchGitHubRepoIssues(params.owner, params.repo, {
        state: issueState,
        limit: 50
      }),
      fetchGitHubRepoPulls(params.owner, params.repo, {
        state: pullState,
        limit: 50
      })
    ]);

    if (issuesResult.status === "fulfilled") {
      issues = issuesResult.value;
    } else {
      issuesError =
        issuesResult.reason instanceof Error
          ? issuesResult.reason.message
          : t(locale, {
              ru: "Не удалось загрузить issues.",
              en: "Failed to load issues."
            });
    }

    if (pullsResult.status === "fulfilled") {
      pulls = pullsResult.value;
    } else {
      pullsError =
        pullsResult.reason instanceof Error
          ? pullsResult.reason.message
          : t(locale, {
              ru: "Не удалось загрузить pull requests.",
              en: "Failed to load pull requests."
            });
    }
  }

  if (repoError || !repo) {
    return (
      <ExecutionPageContainer>
        <Link
          className="inline-flex items-center gap-2 text-sm font-semibold text-brand-700 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200"
          href="/repos"
        >
          <ArrowLeft className="h-4 w-4" />
          {t(locale, { ru: "Назад к репозиториям", en: "Back to repos" })}
        </Link>
        <div className="rounded-3xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-200">
          {repoError}
        </div>
      </ExecutionPageContainer>
    );
  }

  return (
    <ExecutionPageContainer>
      <div className="space-y-3">
        <Link
          className="inline-flex items-center gap-2 text-sm font-semibold text-brand-700 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200"
          href="/repos"
        >
          <ArrowLeft className="h-4 w-4" />
          {t(locale, { ru: "Назад к репозиториям", en: "Back to repos" })}
        </Link>
        <div>
          <h1 className="mb-2 flex items-center gap-3 text-3xl font-black text-slate-900 dark:text-slate-50">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-brand-100 text-brand-700 ring-1 ring-brand-200 dark:bg-zinc-800 dark:text-slate-200 dark:ring-zinc-700">
              <FolderGit2 className="h-5 w-5" />
            </span>
            <span>{repo.full_name}</span>
          </h1>
          <p className="max-w-3xl text-sm text-slate-600 dark:text-slate-300">
            {repo.description ??
              t(locale, {
                ru: "Описание репозитория отсутствует.",
                en: "Repository description is not set."
              })}
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Link
              className="inline-flex items-center gap-2 rounded-full bg-brand-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
              href={`/runs/new?owner=${encodeURIComponent(params.owner)}&repo=${encodeURIComponent(params.repo)}`}
            >
              <PlaySquare className="h-4 w-4" />
              {t(locale, { ru: "Запустить команду", en: "Run team" })}
            </Link>
          </div>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">
              {t(locale, { ru: "Ветка по умолчанию", en: "Default branch" })}
            </p>
            <p className="mt-2 inline-flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
              <GitBranch className="h-4 w-4" />
              {repo.default_branch ?? "-"}
            </p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">
              {t(locale, { ru: "Видимость", en: "Visibility" })}
            </p>
            <p className="mt-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
              {repo.visibility ?? (repo.is_private ? "private" : "public")}
            </p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">
              {t(locale, { ru: "Права текущего gh", en: "Current gh access" })}
            </p>
            <p className="mt-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
              {repo.viewer_permission ?? "-"}
            </p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">
              GitHub
            </p>
            <a
              className="mt-2 inline-flex items-center gap-2 text-sm font-semibold text-brand-700 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200"
              href={repo.url}
              rel="noreferrer"
              target="_blank"
            >
              <ExternalLink className="h-4 w-4" />
              {t(locale, { ru: "Открыть репозиторий", en: "Open repository" })}
            </a>
          </div>
        </div>
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-2xl font-black text-slate-900 dark:text-slate-50">
              {t(locale, { ru: "Pull requests", en: "Pull requests" })}
            </h2>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
              {t(locale, {
                ru: "SCM-срез через host `gh`: metadata, review state и CI checks. Создание draft PR будет привязано к Run flow следующим этапом.",
                en: "SCM slice through host `gh`: metadata, review state, and CI checks. Draft PR creation will be wired into the Run flow next."
              })}
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-full bg-slate-100 p-1 dark:bg-zinc-900/70">
            {(["open", "closed", "merged", "all"] as const).map((value) => {
              const active = value === pullState;
              return (
                <Link
                  className={[
                    "rounded-full px-3 py-1.5 text-xs font-semibold transition",
                    active
                      ? "bg-white text-slate-900 shadow-sm dark:bg-zinc-800 dark:text-slate-50"
                      : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
                  ].join(" ")}
                  href={buildRepoHref(params.owner, params.repo, issueState, value)}
                  key={value}
                >
                  {value}
                </Link>
              );
            })}
          </div>
        </div>

        {pullsError ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-200">
            {pullsError}
          </div>
        ) : null}

        {!pullsError && pulls?.items.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 px-4 py-4 text-sm text-slate-500 dark:border-zinc-700 dark:text-slate-400">
            {t(locale, {
              ru: "Под текущим фильтром pull requests не найдены.",
              en: "No pull requests were found for the current filter."
            })}
          </div>
        ) : null}

        {pulls?.items.length ? (
          <div className="space-y-3">
            {pulls.items.map((pull) => (
              <article
                className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 dark:border-zinc-800 dark:bg-zinc-900/70"
                key={pull.number}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="mb-1 flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">
                      <span>{pull.state}</span>
                      {pull.is_draft ? (
                        <span className="rounded-full bg-slate-200 px-2 py-1 text-[10px] font-semibold text-slate-700 dark:bg-zinc-800 dark:text-slate-200">
                          draft
                        </span>
                      ) : null}
                    </div>
                    <Link
                      className="text-lg font-bold text-slate-900 hover:text-brand-700 dark:text-slate-50 dark:hover:text-brand-300"
                      href={`/repos/${encodeURIComponent(params.owner)}/${encodeURIComponent(params.repo)}/pulls/${pull.number}`}
                    >
                      #{pull.number} {pull.title}
                    </Link>
                  </div>
                  <a
                    className="inline-flex items-center gap-2 text-sm font-semibold text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-slate-50"
                    href={pull.url}
                    rel="noreferrer"
                    target="_blank"
                  >
                    <ExternalLink className="h-4 w-4" />
                    GitHub
                  </a>
                </div>
                <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">{pull.body || "-"}</p>
                <div className="mt-4 flex flex-wrap items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
                  <span className="rounded-full bg-white px-3 py-1 dark:bg-zinc-800">
                    {pull.author_login ?? t(locale, { ru: "автор неизвестен", en: "unknown author" })}
                  </span>
                  <span className="rounded-full bg-white px-3 py-1 dark:bg-zinc-800">
                    {pull.head_ref_name ?? "-"} → {pull.base_ref_name ?? "-"}
                  </span>
                  <span className="rounded-full bg-white px-3 py-1 dark:bg-zinc-800">
                    {pull.review_decision ?? t(locale, { ru: "review не задан", en: "review not set" })}
                  </span>
                  <span className="rounded-full bg-white px-3 py-1 dark:bg-zinc-800">
                    {pull.merge_state_status ?? t(locale, { ru: "merge state не задан", en: "merge state not set" })}
                  </span>
                  <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 dark:bg-zinc-800">
                    <MessageSquareText className="h-3.5 w-3.5" />
                    {pull.comments_count}
                  </span>
                  {pull.labels.map((label) => (
                    <span className="rounded-full bg-white px-3 py-1 dark:bg-zinc-800" key={label}>
                      {label}
                    </span>
                  ))}
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </div>

      <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-2xl font-black text-slate-900 dark:text-slate-50">
              {t(locale, { ru: "Issues", en: "Issues" })}
            </h2>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
              {t(locale, {
                ru: "Tracker-срез через host `gh`. Выбранный issue позже станет входом для Run-сессии.",
                en: "Tracker slice through host `gh`. A selected issue will later become input for a Run session."
              })}
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-full bg-slate-100 p-1 dark:bg-zinc-900/70">
            {(["open", "closed", "all"] as const).map((value) => {
              const active = value === issueState;
              return (
                <Link
                  className={[
                    "rounded-full px-3 py-1.5 text-xs font-semibold transition",
                    active
                      ? "bg-white text-slate-900 shadow-sm dark:bg-zinc-800 dark:text-slate-50"
                      : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
                  ].join(" ")}
                  href={buildRepoHref(params.owner, params.repo, value, pullState)}
                  key={value}
                >
                  {value}
                </Link>
              );
            })}
          </div>
        </div>

        {!repo.has_issues_enabled ? (
          <div className="rounded-2xl border border-dashed border-slate-300 px-4 py-4 text-sm text-slate-500 dark:border-zinc-700 dark:text-slate-400">
            {t(locale, {
              ru: "У этого репозитория issues отключены.",
              en: "Issues are disabled for this repository."
            })}
          </div>
        ) : null}

        {issuesError ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-200">
            {issuesError}
          </div>
        ) : null}

        {repo.has_issues_enabled && !issuesError && issues?.items.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 px-4 py-4 text-sm text-slate-500 dark:border-zinc-700 dark:text-slate-400">
            {t(locale, {
              ru: "Под текущим фильтром issues не найдены.",
              en: "No issues were found for the current filter."
            })}
          </div>
        ) : null}

        {issues?.items.length ? (
          <div className="space-y-3">
            {issues.items.map((issue) => (
              <article
                className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 dark:border-zinc-800 dark:bg-zinc-900/70"
                key={issue.number}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="mb-1 text-xs font-semibold uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">
                      {issue.state}
                    </p>
                    <Link
                      className="text-lg font-bold text-slate-900 hover:text-brand-700 dark:text-slate-50 dark:hover:text-brand-300"
                      href={`/repos/${encodeURIComponent(params.owner)}/${encodeURIComponent(params.repo)}/issues/${issue.number}`}
                    >
                      #{issue.number} {issue.title}
                    </Link>
                  </div>
                  <a
                    className="inline-flex items-center gap-2 text-sm font-semibold text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-slate-50"
                    href={issue.url}
                    rel="noreferrer"
                    target="_blank"
                  >
                    <ExternalLink className="h-4 w-4" />
                    GitHub
                  </a>
                </div>
                <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">{issue.body || "-"}</p>
                <div className="mt-4 flex flex-wrap items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
                  <span className="rounded-full bg-white px-3 py-1 dark:bg-zinc-800">
                    {issue.author_login ?? t(locale, { ru: "автор неизвестен", en: "unknown author" })}
                  </span>
                  <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 dark:bg-zinc-800">
                    <MessageSquareText className="h-3.5 w-3.5" />
                    {issue.comments_count}
                  </span>
                  {issue.labels.map((label) => (
                    <span className="rounded-full bg-white px-3 py-1 dark:bg-zinc-800" key={label}>
                      {label}
                    </span>
                  ))}
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </div>
    </ExecutionPageContainer>
  );
}
