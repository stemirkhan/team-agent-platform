import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { AuthControls } from "@/components/layout/auth-controls";

import "./globals.css";

export const metadata: Metadata = {
  title: "Agent Marketplace",
  description: "MVP marketplace for subagents and agent teams"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body className="font-sans">
        <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-6 py-5">
          <header className="mb-8 flex items-center justify-between border-b border-slate-200 pb-4">
            <Link className="text-xl font-black tracking-tight text-brand-700" href="/">
              Agent Marketplace
            </Link>
            <div className="flex items-center gap-5">
              <nav className="flex items-center gap-5 text-sm font-semibold text-slate-600">
                <Link href="/agents">Agents</Link>
                <Link href="/teams">Teams</Link>
              </nav>
              <AuthControls />
            </div>
          </header>
          <main className="flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}
