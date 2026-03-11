"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Bot, FolderGit2, LayoutDashboard, PlaySquare, UsersRound } from "lucide-react";

import { t, type Locale } from "@/lib/i18n";

function isItemActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function MainNav({ locale }: { locale: Locale }) {
  const pathname = usePathname();
  const navItems = [
    {
      href: "/agents",
      label: t(locale, { ru: "Агенты", en: "Agents" }),
      icon: Bot
    },
    {
      href: "/teams",
      label: t(locale, { ru: "Команды", en: "Teams" }),
      icon: UsersRound
    },
    {
      href: "/diagnostics",
      label: t(locale, { ru: "Диагностика", en: "Diagnostics" }),
      icon: Activity
    },
    {
      href: "/repos",
      label: t(locale, { ru: "Репозитории", en: "Repos" }),
      icon: FolderGit2
    },
    {
      href: "/projects",
      label: t(locale, { ru: "Доска", en: "Board" }),
      icon: LayoutDashboard
    },
    {
      href: "/runs",
      label: t(locale, { ru: "Запуски", en: "Runs" }),
      icon: PlaySquare
    }
  ];

  return (
    <nav className="flex shrink-0 items-center gap-2.5">
      {navItems.map((item) => {
        const active = isItemActive(pathname, item.href);
        const Icon = item.icon;

        return (
          <Link
            className={[
              "inline-flex items-center gap-2.5 rounded-full px-3.5 py-2 text-sm font-semibold transition",
              active
                ? "bg-brand-100 text-brand-800 ring-1 ring-brand-300 dark:bg-zinc-800 dark:text-slate-100 dark:ring-zinc-600"
                : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-zinc-800/80 hover:text-slate-900 dark:hover:text-slate-100"
            ].join(" ")}
            href={item.href}
            key={item.href}
          >
            <Icon className="h-4 w-4" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
