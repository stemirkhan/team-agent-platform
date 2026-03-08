"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bot, Home, UsersRound } from "lucide-react";

import { t, type Locale } from "@/lib/i18n";

function isItemActive(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }

  return pathname === href || pathname.startsWith(`${href}/`);
}

export function MainNav({ locale }: { locale: Locale }) {
  const pathname = usePathname();
  const navItems = [
    {
      href: "/",
      label: t(locale, { ru: "Главная", en: "Home" }),
      icon: Home
    },
    {
      href: "/agents",
      label: t(locale, { ru: "Агенты", en: "Agents" }),
      icon: Bot
    },
    {
      href: "/teams",
      label: t(locale, { ru: "Команды", en: "Teams" }),
      icon: UsersRound
    }
  ];

  return (
    <nav className="flex items-center gap-2">
      {navItems.map((item) => {
        const active = isItemActive(pathname, item.href);
        const Icon = item.icon;

        return (
          <Link
            className={[
              "inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold transition",
              active
                ? "bg-brand-100 text-brand-800 ring-1 ring-brand-300 dark:bg-zinc-800 dark:text-slate-100 dark:ring-zinc-600"
                : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-zinc-800/80 hover:text-slate-900 dark:hover:text-slate-100"
            ].join(" ")}
            href={item.href}
            key={item.href}
          >
            <Icon className="h-3.5 w-3.5" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
