"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { t, type Locale } from "@/lib/i18n";

type Theme = "light" | "dark";

type ThemeToggleProps = {
  locale: Locale;
};

const THEME_STORAGE_KEY = "theme";

function resolveInitialTheme(): Theme {
  if (typeof window === "undefined") {
    return "light";
  }

  const persistedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
  if (persistedTheme === "light" || persistedTheme === "dark") {
    return persistedTheme;
  }

  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
}

export function ThemeToggle({ locale }: ThemeToggleProps) {
  const [theme, setTheme] = useState<Theme>("light");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const initialTheme = resolveInitialTheme();
    setTheme(initialTheme);
    applyTheme(initialTheme);
    setMounted(true);
  }, []);

  function onToggle() {
    const nextTheme: Theme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    applyTheme(nextTheme);
    window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
  }

  const nextModeLabel = theme === "dark"
    ? t(locale, { ru: "светлый", en: "light" })
    : t(locale, { ru: "темный", en: "dark" });
  const currentThemeLabel = theme === "dark"
    ? t(locale, { ru: "темная", en: "dark" })
    : t(locale, { ru: "светлая", en: "light" });

  return (
    <button
      aria-label={
        mounted
          ? t(locale, { ru: `Переключить на ${nextModeLabel} тему`, en: `Switch to ${nextModeLabel} mode` })
          : t(locale, { ru: "Переключить тему", en: "Toggle theme" })
      }
      className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-300 dark:border-zinc-600 text-slate-700 dark:text-slate-200 transition hover:bg-slate-100 dark:hover:bg-zinc-800 hover:text-slate-900 dark:hover:text-slate-100"
      onClick={onToggle}
      title={
        mounted
          ? t(locale, { ru: `Текущая тема: ${currentThemeLabel}`, en: `Current theme: ${currentThemeLabel}` })
          : t(locale, { ru: "Переключить тему", en: "Toggle theme" })
      }
      type="button"
    >
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}
