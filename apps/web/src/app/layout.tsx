import type { Metadata } from "next";
import Link from "next/link";
import { IBM_Plex_Sans, Rubik } from "next/font/google";
import Script from "next/script";
import type { ReactNode } from "react";
import { Compass } from "lucide-react";

import { AuthControls } from "@/components/layout/auth-controls";
import { LocaleToggle } from "@/components/layout/locale-toggle";
import { MainNav } from "@/components/layout/main-nav";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { getRequestLocale } from "@/lib/i18n.server";
import { t } from "@/lib/i18n";

import "./globals.css";

const bodyFont = IBM_Plex_Sans({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
  display: "swap"
});

const headingFont = Rubik({
  subsets: ["latin", "cyrillic"],
  weight: ["500", "600", "700"],
  variable: "--font-heading",
  display: "swap"
});

export const metadata: Metadata = {
  title: "Team Agent Platform",
  description: "Local-first Codex execution platform for GitHub repositories"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  const locale = getRequestLocale();

  return (
    <html lang={locale} suppressHydrationWarning>
      <head>
        <Script id="theme-init" strategy="beforeInteractive">{`(() => {
  try {
    const key = "theme";
    const saved = window.localStorage.getItem(key);
    const preferred =
      saved === "light" || saved === "dark"
        ? saved
        : window.matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark"
          : "light";

    if (preferred === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  } catch {
    document.documentElement.classList.remove("dark");
  }
})();`}</Script>
      </head>
      <body className={`${bodyFont.variable} ${headingFont.variable} font-sans antialiased`}>
        <div className="app-noise fixed inset-0 -z-10 opacity-50" />
        <div className="pointer-events-none fixed inset-x-0 top-0 -z-10 h-80 bg-gradient-to-b from-brand-200/35 to-transparent dark:from-transparent" />
        <div className="mx-auto flex min-h-screen w-full max-w-none flex-col px-6 py-5 md:px-8 xl:px-10">
          <header className="mb-8 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/85 md:px-5">
            <div className="flex items-center justify-between gap-6">
              <Link
                className="inline-flex shrink-0 items-center gap-2 text-xl font-black tracking-tight text-brand-800 dark:text-slate-100"
                href="/"
              >
                <span className="rounded-lg bg-brand-100 p-1.5 text-brand-700 dark:bg-zinc-800 dark:text-slate-300">
                  <Compass className="h-5 w-5" />
                </span>
                Team Agent Platform
              </Link>
              <div className="ml-auto flex items-center gap-3">
                <MainNav locale={locale} />
                <LocaleToggle locale={locale} />
                <ThemeToggle locale={locale} />
                <AuthControls locale={locale} />
              </div>
            </div>
          </header>
          <main className="flex-1 pb-8">
            <div className="mx-auto w-full max-w-[1360px] px-1 sm:px-2 lg:px-4">{children}</div>
          </main>
          <footer className="mt-6 border-t border-slate-200 dark:border-zinc-700/80 py-4 text-xs text-slate-500 dark:text-slate-400">
            {t(locale, {
              ru: "Team Agent Platform: local-first Codex execution поверх GitHub-репозиториев",
              en: "Team Agent Platform: local-first Codex execution over GitHub repositories"
            })}
          </footer>
        </div>
      </body>
    </html>
  );
}
