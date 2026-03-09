import Link from "next/link";
import { ArrowLeft, ExternalLink, MessageSquareText, PlaySquare } from "lucide-react";

import { GitHubIssueTrackerPanel } from "@/components/github/github-issue-tracker-panel";
import { ExecutionPageContainer } from "@/components/layout/execution-page-container";
import { fetchGitHubIssue, fetchGitHubRepo } from "@/lib/api";
import { t } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n.server";

export default async function RepoIssuePage({
  params
}: {
  params: { owner: string; repo: string; number: string };
}) {
  const locale = getRequestLocale();
  const issueNumber = Number(params.number);

  let issue = null;
  let repo = null;
  let error: string | null = null;

  try {
    [repo, issue] = await Promise.all([
      fetchGitHubRepo(params.owner, params.repo),
      fetchGitHubIssue(params.owner, params.repo, issueNumber)
    ]);
  } catch (fetchError) {
    error =
      fetchError instanceof Error
        ? fetchError.message
        : t(locale, {
            ru: "Не удалось загрузить issue.",
            en: "Failed to load issue."
          });
  }

  return (
    <ExecutionPageContainer>
      <Link
        className="inline-flex items-center gap-2 text-sm font-semibold text-brand-700 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200"
        href={`/repos/${encodeURIComponent(params.owner)}/${encodeURIComponent(params.repo)}`}
      >
        <ArrowLeft className="h-4 w-4" />
        {t(locale, { ru: "Назад к репозиторию", en: "Back to repository" })}
      </Link>

      {error || !issue || !repo ? (
        <div className="rounded-3xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-200">
          {error}
        </div>
      ) : (
        <>
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">
              {repo.full_name}
            </p>
            <h1 className="text-3xl font-black text-slate-900 dark:text-slate-50">
              #{issue.number} {issue.title}
            </h1>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
              <span className="rounded-full bg-slate-100 px-3 py-1 dark:bg-zinc-800">{issue.state}</span>
              <span className="rounded-full bg-slate-100 px-3 py-1 dark:bg-zinc-800">
                {issue.author_login ?? t(locale, { ru: "автор неизвестен", en: "unknown author" })}
              </span>
              <span className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 dark:bg-zinc-800">
                <MessageSquareText className="h-3.5 w-3.5" />
                {issue.comments_count}
              </span>
              {issue.labels.map((label) => (
                <span className="rounded-full bg-slate-100 px-3 py-1 dark:bg-zinc-800" key={label}>
                  {label}
                </span>
              ))}
            </div>
            <div className="mt-4">
              <Link
                className="inline-flex items-center gap-2 rounded-full bg-brand-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
                href={`/runs/new?owner=${encodeURIComponent(params.owner)}&repo=${encodeURIComponent(params.repo)}&issue=${issue.number}`}
              >
                <PlaySquare className="h-4 w-4" />
                {t(locale, { ru: "Запустить команду по issue", en: "Run team on issue" })}
              </Link>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-xl font-black text-slate-900 dark:text-slate-50">
                {t(locale, { ru: "Текст issue", en: "Issue body" })}
              </h2>
              <a
                className="inline-flex items-center gap-2 text-sm font-semibold text-brand-700 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200"
                href={issue.url}
                rel="noreferrer"
                target="_blank"
              >
                <ExternalLink className="h-4 w-4" />
                GitHub
              </a>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-sm leading-7 text-slate-700 dark:border-zinc-800 dark:bg-zinc-900/70 dark:text-slate-200">
              <pre className="whitespace-pre-wrap font-sans">{issue.body || "-"}</pre>
            </div>
          </div>

          <GitHubIssueTrackerPanel
            initialIssue={issue}
            issueNumber={issue.number}
            locale={locale}
            owner={params.owner}
            repo={params.repo}
          />
        </>
      )}
    </ExecutionPageContainer>
  );
}
