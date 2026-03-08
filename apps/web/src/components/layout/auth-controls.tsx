"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { LogIn, LogOut, UserPlus } from "lucide-react";

import {
  clearAccessToken,
  fetchCurrentUser,
  getAccessToken,
  type AuthUser
} from "@/lib/auth-client";
import { t, type Locale } from "@/lib/i18n";

type AuthState = {
  loading: boolean;
  user: AuthUser | null;
};

export function AuthControls({ locale }: { locale: Locale }) {
  const pathname = usePathname();
  const [state, setState] = useState<AuthState>({ loading: false, user: null });

  useEffect(() => {
    let cancelled = false;

    async function resolveUser() {
      const token = getAccessToken();
      if (!token) {
        if (!cancelled) {
          setState({ loading: false, user: null });
        }
        return;
      }

      if (!cancelled) {
        setState({ loading: true, user: null });
      }

      try {
        const user = await fetchCurrentUser(token);
        if (!cancelled) {
          setState({ loading: false, user });
        }
      } catch {
        clearAccessToken();
        if (!cancelled) {
          setState({ loading: false, user: null });
        }
      }
    }

    void resolveUser();

    return () => {
      cancelled = true;
    };
  }, [pathname]);

  if (state.loading) {
    return <span className="text-xs text-slate-500 dark:text-slate-400">{t(locale, { ru: "авторизация...", en: "auth..." })}</span>;
  }

  if (!state.user) {
    return (
      <div className="flex shrink-0 items-center gap-2">
        <Link
          className="inline-flex items-center gap-1.5 rounded-full border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100 dark:border-zinc-600 dark:text-slate-200 dark:hover:bg-zinc-800"
          href="/auth/login"
        >
          <LogIn className="h-3.5 w-3.5" />
          {t(locale, { ru: "Войти", en: "Login" })}
        </Link>
        <Link
          className="inline-flex items-center gap-1.5 rounded-full bg-brand-700 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-brand-800 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
          href="/auth/register"
        >
          <UserPlus className="h-3.5 w-3.5" />
          {t(locale, { ru: "Регистрация", en: "Register" })}
        </Link>
      </div>
    );
  }

  return (
    <div className="flex shrink-0 items-center gap-2">
      <span className="hidden max-w-40 truncate rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700 dark:bg-zinc-800 dark:text-slate-200 lg:inline-flex">
        {state.user.display_name}
      </span>
      <button
        className="inline-flex items-center gap-1.5 rounded-full border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100 dark:border-zinc-600 dark:text-slate-200 dark:hover:bg-zinc-800"
        onClick={() => {
          clearAccessToken();
          setState({ loading: false, user: null });
        }}
        type="button"
      >
        <LogOut className="h-3.5 w-3.5" />
        {t(locale, { ru: "Выйти", en: "Logout" })}
      </button>
    </div>
  );
}
