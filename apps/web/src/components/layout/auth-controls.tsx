"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

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
          className="rounded-md border border-slate-300 px-3 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100"
          href="/auth/login"
        >
          Login
        </Link>
        <Link
          className="rounded-md bg-brand-600 px-3 py-1 text-xs font-semibold text-white hover:bg-brand-700"
          href="/auth/register"
        >
          Register
        </Link>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <span className="text-xs font-semibold text-slate-600">{state.user.display_name}</span>
      <button
        className="rounded-md border border-slate-300 px-3 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-100"
        onClick={() => {
          clearAccessToken();
          setState({ loading: false, user: null });
        }}
        type="button"
      >
        Logout
      </button>
    </div>
  );
}
