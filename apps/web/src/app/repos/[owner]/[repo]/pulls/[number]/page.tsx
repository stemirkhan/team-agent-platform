import Link from "next/link";
import { ArrowLeft, ExternalLink, GitBranch, ShieldCheck } from "lucide-react";

import { ExecutionPageContainer } from "@/components/layout/execution-page-container";
import { fetchGitHubPull, fetchGitHubPullChecks, fetchGitHubRepo } from "@/lib/api";
import { t } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n.server";

function checkBucketClasses(bucket: string | null): string {
  switch (bucket) {
    case "pass":
      return "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300";
    case "fail":
      return "bg-rose-100 text-rose-800 dark:bg-rose-500/10 dark:text-rose-300";
    case "pending":
      return "bg-amber-100 text-amber-800 dark:bg-amber-500/10 dark:text-amber-300";
    case "cancel":
      return "bg-slate-200 text-slate-700 dark:bg-zinc-800 dark:text-slate-200";
    case "skipping":
    default:
      return "bg-slate-100 text-slate-700 dark:bg-zinc-800 dark:text-slate-200";
  }
}

export default async function RepoPullPage({
  params
}: {
  params: { owner: string; repo: string; number: string };
}) {
  const locale = getRequestLocale();
  const pullNumber = Number(params.number);

  let pull = null;
  let repo = null;
  let checks = null;
  let error: string | null = null;

  try {
    [repo, pull, checks] = await Promise.all([
      fetchGitHubRepo(params.owner, params.repo),
      fetchGitHubPull(params.owner, params.repo, pullNumber),
      fetchGitHubPullChecks(params.owner, params.repo, pullNumber)
    ]);
  } catch (fetchError) {
    error =
      fetchError instanceof Error
        ? fetchError.message
        : t(locale, {
            ru: "Не удалось загрузить pull request.",
            en: "Failed to load pull request."
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

      {error || !pull || !repo || !checks ? (
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
              PR #{pull.number} {pull.title}
            </h1>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
              <span className="rounded-full bg-slate-100 px-3 py-1 dark:bg-zinc-800">{pull.state}</span>
              {pull.is_draft ? (
                <span className="rounded-full bg-slate-100 px-3 py-1 dark:bg-zinc-800">
                  {t(locale, { ru: "draft", en: "draft" })}
                </span>
              ) : null}
              <span className="rounded-full bg-slate-100 px-3 py-1 dark:bg-zinc-800">
                {pull.author_login ?? t(locale, { ru: "автор неизвестен", en: "unknown author" })}
              </span>
              <span className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 dark:bg-zinc-800">
                <GitBranch className="h-3.5 w-3.5" />
                {pull.head_ref_name ?? "-"} → {pull.base_ref_name ?? "-"}
              </span>
              {pull.labels.map((label) => (
                <span className="rounded-full bg-slate-100 px-3 py-1 dark:bg-zinc-800" key={label}>
                  {label}
                </span>
              ))}
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">
                  {t(locale, { ru: "Merge state", en: "Merge state" })}
                </p>
                <p className="mt-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
                  {pull.merge_state_status ?? "-"}
                </p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">
                  {t(locale, { ru: "Mergeable", en: "Mergeable" })}
                </p>
                <p className="mt-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
                  {pull.mergeable ?? "-"}
                </p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">
                  {t(locale, { ru: "Review decision", en: "Review decision" })}
                </p>
                <p className="mt-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
                  {pull.review_decision ?? "-"}
                </p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">
                  GitHub
                </p>
                <a
                  className="mt-2 inline-flex items-center gap-2 text-sm font-semibold text-brand-700 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200"
                  href={pull.url}
                  rel="noreferrer"
                  target="_blank"
                >
                  <ExternalLink className="h-4 w-4" />
                  {t(locale, { ru: "Открыть pull request", en: "Open pull request" })}
                </a>
              </div>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-xl font-black text-slate-900 dark:text-slate-50">
                {t(locale, { ru: "Текст pull request", en: "Pull request body" })}
              </h2>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600 dark:bg-zinc-900/70 dark:text-slate-300">
                {t(locale, {
                  ru: `${pull.comments_count} комментариев`,
                  en: `${pull.comments_count} comments`
                })}
              </span>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-sm leading-7 text-slate-700 dark:border-zinc-800 dark:bg-zinc-900/70 dark:text-slate-200">
              <pre className="whitespace-pre-wrap font-sans">{pull.body || "-"}</pre>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-black text-slate-900 dark:text-slate-50">
                  {t(locale, { ru: "Checks", en: "Checks" })}
                </h2>
                <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                  {t(locale, {
                    ru: "Нормализованный CI/status summary через `gh pr checks`.",
                    en: "Normalized CI/status summary through `gh pr checks`."
                  })}
                </p>
              </div>
              <div className="flex flex-wrap gap-2 text-xs font-semibold">
                <span className="rounded-full bg-emerald-100 px-3 py-1 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300">
                  pass: {checks.summary.pass_count}
                </span>
                <span className="rounded-full bg-rose-100 px-3 py-1 text-rose-800 dark:bg-rose-500/10 dark:text-rose-300">
                  fail: {checks.summary.fail_count}
                </span>
                <span className="rounded-full bg-amber-100 px-3 py-1 text-amber-800 dark:bg-amber-500/10 dark:text-amber-300">
                  pending: {checks.summary.pending_count}
                </span>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-700 dark:bg-zinc-800 dark:text-slate-200">
                  skipping: {checks.summary.skipping_count}
                </span>
              </div>
            </div>

            {checks.items.length > 0 ? (
              <div className="space-y-3">
                {checks.items.map((check) => (
                  <article
                    className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 dark:border-zinc-800 dark:bg-zinc-900/70"
                    key={`${check.workflow ?? "workflow"}-${check.name}-${check.started_at ?? "unknown"}`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="mb-1 flex items-center gap-2">
                          <ShieldCheck className="h-4 w-4 text-slate-500 dark:text-slate-400" />
                          <h3 className="text-base font-bold text-slate-900 dark:text-slate-50">
                            {check.name}
                          </h3>
                        </div>
                        <p className="text-sm text-slate-600 dark:text-slate-300">
                          {check.workflow ?? t(locale, { ru: "workflow не указан", en: "workflow unavailable" })}
                        </p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${checkBucketClasses(check.bucket)}`}>
                        {check.bucket ?? check.state}
                      </span>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
                      <span className="rounded-full bg-white px-3 py-1 dark:bg-zinc-800">{check.state}</span>
                      {check.event ? (
                        <span className="rounded-full bg-white px-3 py-1 dark:bg-zinc-800">{check.event}</span>
                      ) : null}
                      {check.description ? (
                        <span className="rounded-full bg-white px-3 py-1 dark:bg-zinc-800">{check.description}</span>
                      ) : null}
                    </div>
                    {check.link ? (
                      <a
                        className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-brand-700 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200"
                        href={check.link}
                        rel="noreferrer"
                        target="_blank"
                      >
                        <ExternalLink className="h-4 w-4" />
                        {t(locale, { ru: "Открыть check", en: "Open check" })}
                      </a>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-300 px-4 py-4 text-sm text-slate-500 dark:border-zinc-700 dark:text-slate-400">
                {t(locale, {
                  ru: "Для этого pull request checks пока не найдены.",
                  en: "No checks were reported for this pull request yet."
                })}
              </div>
            )}
          </div>
        </>
      )}
    </ExecutionPageContainer>
  );
}
