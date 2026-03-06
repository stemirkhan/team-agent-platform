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

type AuthState = {
  loading: boolean;
  user: AuthUser | null;
};

export function AuthControls() {
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
    return <span className="text-xs text-slate-500">auth...</span>;
  }

  if (!state.user) {
    return (
      <div className="flex items-center gap-2">
        <Link
          className="inline-flex items-center gap-1.5 rounded-full border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100"
          href="/auth/login"
        >
          <LogIn className="h-3.5 w-3.5" />
          Login
        </Link>
        <Link
          className="inline-flex items-center gap-1.5 rounded-full bg-brand-700 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-brand-800"
          href="/auth/register"
        >
          <UserPlus className="h-3.5 w-3.5" />
          Register
        </Link>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
        {state.user.display_name}
      </span>
      <button
        className="inline-flex items-center gap-1.5 rounded-full border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100"
        onClick={() => {
          clearAccessToken();
          setState({ loading: false, user: null });
        }}
        type="button"
      >
        <LogOut className="h-3.5 w-3.5" />
        Logout
      </button>
    </div>
  );
}
