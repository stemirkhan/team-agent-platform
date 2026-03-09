import Link from "next/link";
import { ExternalLink, FolderGit2, GitBranch, Search } from "lucide-react";

import { ExecutionPageContainer } from "@/components/layout/execution-page-container";
import { fetchGitHubRepos } from "@/lib/api";
import { t } from "@/lib/i18n";
import { getRequestLocale } from "@/lib/i18n.server";

function readSearchValue(value: string | string[] | undefined): string {
  if (Array.isArray(value)) {
    return value[0]?.trim() ?? "";
  }
  return value?.trim() ?? "";
}

export default async function ReposPage({
  searchParams
}: {
  searchParams?: { owner?: string | string[]; q?: string | string[] };
}) {
  const locale = getRequestLocale();
  const owner = readSearchValue(searchParams?.owner);
  const query = readSearchValue(searchParams?.q);

  let data = null;
  let error: string | null = null;

  try {
    data = await fetchGitHubRepos({
      owner: owner || undefined,
      q: query || undefined,
      limit: 50
    });
  } catch (fetchError) {
    error =
      fetchError instanceof Error
        ? fetchError.message
        : t(locale, {
            ru: "Не удалось загрузить список репозиториев.",
            en: "Failed to load repositories."
          });
  }

  return (
    <ExecutionPageContainer>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="mb-2 flex items-center gap-3 text-3xl font-black text-slate-900 dark:text-slate-50">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-brand-100 text-brand-700 ring-1 ring-brand-200 dark:bg-zinc-800 dark:text-slate-200 dark:ring-zinc-700">
              <FolderGit2 className="h-5 w-5" />
            </span>
            <span>{t(locale, { ru: "GitHub репозитории", en: "GitHub Repositories" })}</span>
          </h1>
          <p className="max-w-3xl text-sm text-slate-600 dark:text-slate-300">
            {t(locale, {
              ru: "Первый read-only слой поверх host `gh`: список доступных репозиториев и быстрый переход к issues.",
              en: "The first read-only layer over host `gh`: browse visible repositories and drill into issues."
            })}
          </p>
        </div>
      </div>

      <form className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
        <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] md:items-end">
          <label className="space-y-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
            <span>{t(locale, { ru: "Owner / org", en: "Owner / org" })}</span>
            <input
              className="w-full rounded-2xl border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-900 outline-none ring-0 transition placeholder:text-slate-400 focus:border-brand-400 dark:border-zinc-700 dark:bg-zinc-900/70 dark:text-slate-50 dark:placeholder:text-slate-500"
              defaultValue={owner}
              name="owner"
              placeholder={t(locale, { ru: "например, stemirkhan", en: "for example, stemirkhan" })}
            />
          </label>
          <label className="space-y-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
            <span>{t(locale, { ru: "Поиск", en: "Search" })}</span>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                className="w-full rounded-2xl border border-slate-300 bg-white py-2.5 pl-10 pr-4 text-sm text-slate-900 outline-none ring-0 transition placeholder:text-slate-400 focus:border-brand-400 dark:border-zinc-700 dark:bg-zinc-900/70 dark:text-slate-50 dark:placeholder:text-slate-500"
                defaultValue={query}
                name="q"
                placeholder={t(locale, { ru: "repo, owner или описание", en: "repo, owner, or description" })}
              />
            </div>
          </label>
          <button className="inline-flex h-11 items-center justify-center rounded-2xl bg-brand-700 px-5 text-sm font-semibold text-white transition hover:bg-brand-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white" type="submit">
            {t(locale, { ru: "Обновить", en: "Refresh" })}
          </button>
        </div>
      </form>

      {error ? (
        <div className="rounded-3xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-200">
          {error}
        </div>
      ) : null}

      {!error && data?.items.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-slate-300 bg-white px-5 py-6 text-sm text-slate-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-slate-400">
          {t(locale, {
            ru: "Репозитории не найдены. Проверь `gh auth status`, owner-фильтр или видимость репозиториев в текущем GitHub-аккаунте.",
            en: "No repositories were found. Check `gh auth status`, the owner filter, or repository visibility for the current GitHub account."
          })}
        </div>
      ) : null}

      {data?.items.length ? (
        <div className="grid gap-4 xl:grid-cols-2">
          {data.items.map((repo) => (
            <article
              className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20"
              key={repo.full_name}
            >
              <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">
                    {repo.visibility ?? (repo.is_private ? "private" : "public")}
                  </p>
                  <h2 className="text-xl font-bold text-slate-900 dark:text-slate-50">{repo.full_name}</h2>
                </div>
                <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700 dark:bg-zinc-800 dark:text-slate-200">
                  {repo.viewer_permission ?? t(locale, { ru: "нет прав", en: "no access" })}
                </span>
              </div>

              <p className="min-h-[3rem] text-sm text-slate-600 dark:text-slate-300">
                {repo.description ??
                  t(locale, {
                    ru: "Описание репозитория отсутствует.",
                    en: "Repository description is not set."
                  })}
              </p>

              <div className="mt-4 flex flex-wrap gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
                <span className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 dark:bg-zinc-800">
                  <GitBranch className="h-3.5 w-3.5" />
                  {repo.default_branch ?? "-"}
                </span>
                <span className="rounded-full bg-slate-100 px-3 py-1 dark:bg-zinc-800">
                  {repo.has_issues_enabled
                    ? t(locale, { ru: "issues включены", en: "issues enabled" })
                    : t(locale, { ru: "issues отключены", en: "issues disabled" })}
                </span>
              </div>

              <div className="mt-5 flex flex-wrap items-center gap-3 text-sm font-semibold">
                <Link
                  className="inline-flex items-center gap-2 text-brand-700 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200"
                  href={`/repos/${encodeURIComponent(repo.owner)}/${encodeURIComponent(repo.name)}`}
                >
                  {t(locale, { ru: "Открыть в приложении", en: "Open in app" })}
                </Link>
                <a
                  className="inline-flex items-center gap-2 text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-slate-50"
                  href={repo.url}
                  rel="noreferrer"
                  target="_blank"
                >
                  <ExternalLink className="h-4 w-4" />
                  GitHub
                </a>
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </ExecutionPageContainer>
  );
}
