import type { Metadata } from "next";
import Link from "next/link";
import { IBM_Plex_Sans, Space_Grotesk } from "next/font/google";
import Script from "next/script";
import type { ReactNode } from "react";
import { Compass } from "lucide-react";

import { AuthControls } from "@/components/layout/auth-controls";
import { MainNav } from "@/components/layout/main-nav";
import { ThemeToggle } from "@/components/layout/theme-toggle";

import "./globals.css";

const bodyFont = IBM_Plex_Sans({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
  display: "swap"
});

const headingFont = Space_Grotesk({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-heading",
  display: "swap"
});

export const metadata: Metadata = {
  title: "Agent Marketplace",
  description: "MVP marketplace for subagents and agent teams"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru" suppressHydrationWarning>
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
        <div className="pointer-events-none fixed inset-x-0 top-0 -z-10 h-80 bg-gradient-to-b from-brand-200/35 to-transparent dark:from-brand-900/30" />
        <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-6 py-5 md:px-8">
          <header className="mb-8 rounded-2xl border border-slate-200 dark:border-slate-700/80 bg-white dark:bg-slate-900/80 px-4 py-3 shadow-sm backdrop-blur md:px-5">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <Link
                className="inline-flex items-center gap-2 text-xl font-black tracking-tight text-brand-800 dark:text-brand-200"
                href="/"
              >
                <span className="rounded-lg bg-brand-100 p-1.5 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300">
                  <Compass className="h-5 w-5" />
                </span>
                Agent Marketplace
              </Link>
              <div className="flex items-center gap-4">
                <MainNav />
                <ThemeToggle />
                <AuthControls />
              </div>
            </div>
          </header>
          <main className="flex-1 pb-8">{children}</main>
          <footer className="mt-6 border-t border-slate-200 dark:border-slate-700/80 py-4 text-xs text-slate-500 dark:text-slate-400">
            Marketplace MVP for subagents and teams
          </footer>
        </div>
      </body>
    </html>
  );
}
