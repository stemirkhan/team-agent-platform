import Link from "next/link";
import { ArrowLeft, PlaySquare } from "lucide-react";

import { ExecutionPageContainer } from "@/components/layout/execution-page-container";
import { RunLaunchForm } from "@/components/runs/run-launch-form";
import { fetchGitHubRepos, fetchHostReadiness, fetchTeams } from "@/lib/api";
import { t } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n.server";

function firstValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function NewRunPage({
  searchParams
}: {
  searchParams?: {
    owner?: string | string[];
    repo?: string | string[];
    issue?: string | string[];
    team?: string | string[];
  };
}) {
  const locale = getRequestLocale();

  const [teamsResult, reposResult, readinessResult] = await Promise.allSettled([
    fetchTeams(),
    fetchGitHubRepos({ limit: 20 }),
    fetchHostReadiness()
  ]);

  const teams = teamsResult.status === "fulfilled" ? teamsResult.value.items : [];
  const repos = reposResult.status === "fulfilled" ? reposResult.value.items : [];
  const readiness = readinessResult.status === "fulfilled" ? readinessResult.value : null;

  const issueRaw = firstValue(searchParams?.issue);
  const issueNumber = issueRaw ? Number(issueRaw) : undefined;

  return (
    <ExecutionPageContainer>
      <div className="space-y-3">
        <Link
          className="inline-flex items-center gap-2 text-sm font-semibold text-brand-700 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200"
          href="/runs"
        >
          <ArrowLeft className="h-4 w-4" />
          {t(locale, { ru: "Назад к запускам", en: "Back to runs" })}
        </Link>
        <div>
          <h1 className="mb-2 flex items-center gap-3 text-3xl font-black text-slate-900 dark:text-slate-50">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-brand-100 text-brand-700 ring-1 ring-brand-200 dark:bg-zinc-800 dark:text-slate-200 dark:ring-zinc-700">
              <PlaySquare className="h-5 w-5" />
            </span>
            <span>{t(locale, { ru: "Запустить команду", en: "Run team" })}</span>
          </h1>
          <p className="max-w-3xl text-sm text-slate-600 dark:text-slate-300">
            {t(locale, {
              ru: "Форма собирает repo target, task context и runtime-параметры Codex. После submit платформа готовит workspace и сразу стартует host-side run.",
              en: "This form collects the repo target, task context, and Codex runtime parameters. After submit, the platform prepares the workspace and starts the host-side run immediately."
            })}
          </p>
        </div>
      </div>

      <RunLaunchForm
        initialIssueNumber={Number.isFinite(issueNumber) ? issueNumber : undefined}
        initialOwner={firstValue(searchParams?.owner)}
        initialRepo={firstValue(searchParams?.repo)}
        initialTeamSlug={firstValue(searchParams?.team)}
        locale={locale}
        readiness={readiness}
        suggestedRepos={repos}
        teams={teams}
      />
    </ExecutionPageContainer>
  );
}
