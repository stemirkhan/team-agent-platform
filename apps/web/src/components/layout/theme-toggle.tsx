"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

type Theme = "light" | "dark";

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

export function ThemeToggle() {
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

  return (
    <button
      aria-label={mounted ? `Switch to ${theme === "dark" ? "light" : "dark"} mode` : "Toggle theme"}
      className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200 transition hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100"
      onClick={onToggle}
      title={mounted ? `Current theme: ${theme}` : "Toggle theme"}
      type="button"
    >
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}
