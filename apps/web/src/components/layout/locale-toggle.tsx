"use client";

import { Languages } from "lucide-react";
import { useRouter } from "next/navigation";

import { LOCALE_COOKIE_NAME, type Locale } from "@/lib/i18n";

type LocaleToggleProps = {
  locale: Locale;
};

export function LocaleToggle({ locale }: LocaleToggleProps) {
  const router = useRouter();

  function updateLocale(nextLocale: Locale) {
    if (nextLocale === locale) {
      return;
    }

    document.cookie = `${LOCALE_COOKIE_NAME}=${nextLocale}; path=/; max-age=31536000; samesite=lax`;
    document.documentElement.lang = nextLocale;
    router.refresh();
  }

  return (
    <div className="inline-flex items-center gap-1 rounded-full border border-slate-300 px-1 py-1 dark:border-zinc-600">
      <span className="inline-flex h-7 w-7 items-center justify-center rounded-full text-slate-500 dark:text-slate-300">
        <Languages className="h-4 w-4" />
      </span>
      {(["ru", "en"] as const).map((option) => (
        <button
          className={[
            "rounded-full px-2.5 py-1 text-xs font-semibold uppercase transition",
            option === locale
              ? "bg-brand-100 text-brand-800 dark:bg-zinc-800 dark:text-slate-100"
              : "text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-zinc-800 dark:hover:text-white"
          ].join(" ")}
          key={option}
          onClick={() => updateLocale(option)}
          type="button"
        >
          {option}
        </button>
      ))}
    </div>
  );
}
