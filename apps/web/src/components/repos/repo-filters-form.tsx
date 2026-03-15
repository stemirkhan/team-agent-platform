"use client";

import { useCallback, useEffect, useRef, useState, useTransition, type FormEvent } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Search } from "lucide-react";

import { t, type Locale } from "@/lib/i18n";

const FILTER_SUBMIT_DEBOUNCE_MS = 400;

type RepoFiltersFormProps = {
  locale: Locale;
  owner: string;
  query: string;
};

export function RepoFiltersForm({ locale, owner: initialOwner, query: initialQuery }: RepoFiltersFormProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  const [owner, setOwner] = useState(initialOwner);
  const [query, setQuery] = useState(initialQuery);
  const latestAppliedRef = useRef(`${initialOwner}\n${initialQuery}`);

  useEffect(() => {
    const incomingSignature = `${initialOwner}\n${initialQuery}`;
    if (incomingSignature === latestAppliedRef.current) {
      return;
    }

    setOwner(initialOwner);
    setQuery(initialQuery);
    latestAppliedRef.current = incomingSignature;
  }, [initialOwner, initialQuery]);

  const applyFilters = useCallback(
    (nextOwnerRaw: string, nextQueryRaw: string) => {
      const nextOwner = nextOwnerRaw.trim();
      const nextQuery = nextQueryRaw.trim();
      const nextParams = new URLSearchParams(searchParams.toString());

      if (nextOwner.length > 0) {
        nextParams.set("owner", nextOwner);
      } else {
        nextParams.delete("owner");
      }

      if (nextQuery.length > 0) {
        nextParams.set("q", nextQuery);
      } else {
        nextParams.delete("q");
      }

      const nextQueryString = nextParams.toString();
      const currentQueryString = searchParams.toString();
      if (nextQueryString === currentQueryString) {
        return;
      }

      latestAppliedRef.current = `${nextOwner}\n${nextQuery}`;
      const nextHref = nextQueryString ? `${pathname}?${nextQueryString}` : pathname;
      startTransition(() => {
        router.replace(nextHref, { scroll: false });
      });
    },
    [pathname, router, searchParams]
  );

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      applyFilters(owner, query);
    }, FILTER_SUBMIT_DEBOUNCE_MS);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [applyFilters, owner, query]);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    applyFilters(owner, query);
  }

  return (
    <form
      aria-busy={isPending}
      className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20"
      onSubmit={onSubmit}
    >
      <div className="grid gap-4 md:grid-cols-2 md:items-end">
        <label className="space-y-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
          <span>{t(locale, { ru: "Owner / org", en: "Owner / org" })}</span>
          <input
            className="w-full rounded-2xl border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-900 outline-none ring-0 transition placeholder:text-slate-400 focus:border-brand-400 dark:border-zinc-700 dark:bg-zinc-900/70 dark:text-slate-50 dark:placeholder:text-slate-500"
            name="owner"
            onChange={(event) => setOwner(event.target.value)}
            placeholder={t(locale, { ru: "например, stemirkhan", en: "for example, stemirkhan" })}
            value={owner}
          />
        </label>
        <label className="space-y-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
          <span>{t(locale, { ru: "Поиск", en: "Search" })}</span>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              className="w-full rounded-2xl border border-slate-300 bg-white py-2.5 pl-10 pr-4 text-sm text-slate-900 outline-none ring-0 transition placeholder:text-slate-400 focus:border-brand-400 dark:border-zinc-700 dark:bg-zinc-900/70 dark:text-slate-50 dark:placeholder:text-slate-500"
              name="q"
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t(locale, { ru: "repo, owner или описание", en: "repo, owner, or description" })}
              value={query}
            />
          </div>
        </label>
      </div>
      <p aria-live="polite" className="mt-3 text-xs text-slate-500 dark:text-slate-400">
        {isPending
          ? t(locale, { ru: "Обновляем список репозиториев...", en: "Updating repositories..." })
          : t(locale, { ru: "Фильтры применяются автоматически.", en: "Filters are applied automatically." })}
      </p>
    </form>
  );
}
