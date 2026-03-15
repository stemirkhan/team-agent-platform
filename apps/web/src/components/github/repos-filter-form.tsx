"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { t, type Locale } from "@/lib/i18n";

type ReposFilterFormProps = {
  initialOwner: string;
  initialQuery: string;
  locale: Locale;
};

export function ReposFilterForm({ initialOwner, initialQuery, locale }: ReposFilterFormProps) {
  const router = useRouter();
  const [owner, setOwner] = useState(initialOwner);
  const [query, setQuery] = useState(initialQuery);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // On mount sync state with props so navigating back/forward keeps inputs in sync.
  useEffect(() => {
    setOwner(initialOwner);
    setQuery(initialQuery);
  }, [initialOwner, initialQuery]);

  useEffect(() => {
    if (debounceRef.current !== null) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(() => {
      const params = new URLSearchParams();
      if (owner.trim()) params.set("owner", owner.trim());
      if (query.trim()) params.set("q", query.trim());
      router.push(`/repos${params.size > 0 ? `?${params.toString()}` : ""}`);
    }, 400);

    return () => {
      if (debounceRef.current !== null) {
        clearTimeout(debounceRef.current);
      }
    };
    // Intentional: only re-run when filter values change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [owner, query]);

  return (
    <form
      className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20"
      onSubmit={(e) => {
        e.preventDefault();
        if (debounceRef.current !== null) {
          clearTimeout(debounceRef.current);
        }
        const params = new URLSearchParams();
        if (owner.trim()) params.set("owner", owner.trim());
        if (query.trim()) params.set("q", query.trim());
        router.push(`/repos${params.size > 0 ? `?${params.toString()}` : ""}`);
      }}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
          <span>{t(locale, { ru: "Owner / org", en: "Owner / org" })}</span>
          <input
            className="w-full rounded-2xl border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-900 outline-none ring-0 transition placeholder:text-slate-400 focus:border-brand-400 dark:border-zinc-700 dark:bg-zinc-900/70 dark:text-slate-50 dark:placeholder:text-slate-500"
            name="owner"
            onChange={(e) => setOwner(e.target.value)}
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
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t(locale, { ru: "repo, owner или описание", en: "repo, owner, or description" })}
              value={query}
            />
          </div>
        </label>
      </div>
    </form>
  );
}
