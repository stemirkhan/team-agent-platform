"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { KeyRound, Mail, UserRound, UserRoundPlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { registerWithPassword, setAccessToken } from "@/lib/auth-client";

export default function RegisterPage() {
  const router = useRouter();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setErrorMessage(null);

    try {
      const result = await registerWithPassword({
        display_name: displayName.trim(),
        email: email.trim(),
        password
      });

      setAccessToken(result.access_token);
      router.push("/");
      router.refresh();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Registration failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="mx-auto max-w-md rounded-3xl border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900/95 p-6 shadow-lg shadow-slate-200/60">
      <p className="mb-3 inline-flex items-center gap-2 rounded-full bg-brand-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-brand-800">
        <UserRoundPlus className="h-3.5 w-3.5" />
        Auth
      </p>
      <h1 className="mb-2 text-2xl font-black text-slate-900 dark:text-slate-50">Register</h1>
      <p className="mb-6 text-sm text-slate-600 dark:text-slate-300">Create your account to publish and compose teams.</p>

      <form className="space-y-4" onSubmit={onSubmit}>
        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          Display name
          <div className="relative mt-1">
            <input
              className="w-full rounded-xl border border-slate-300 dark:border-zinc-600 bg-white dark:bg-zinc-900 px-3 py-2 pr-10 text-sm outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-200"
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="Your name"
              required
              type="text"
              value={displayName}
            />
            <UserRound className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          </div>
        </label>

        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          Email
          <div className="relative mt-1">
            <input
              className="w-full rounded-xl border border-slate-300 dark:border-zinc-600 bg-white dark:bg-zinc-900 px-3 py-2 pr-10 text-sm outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-200"
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              required
              type="email"
              value={email}
            />
            <Mail className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          </div>
        </label>

        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          Password
          <div className="relative mt-1">
            <input
              className="w-full rounded-xl border border-slate-300 dark:border-zinc-600 bg-white dark:bg-zinc-900 px-3 py-2 pr-10 text-sm outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-200"
              minLength={8}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="At least 8 characters"
              required
              type="password"
              value={password}
            />
            <KeyRound className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          </div>
        </label>

        {errorMessage ? (
          <p className="rounded-lg border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {errorMessage}
          </p>
        ) : null}

        <Button disabled={submitting} type="submit">
          {submitting ? "Creating account..." : "Create account"}
        </Button>
      </form>

      <p className="mt-4 text-sm text-slate-600 dark:text-slate-300">
        Already registered?{" "}
        <Link className="font-semibold text-brand-700 hover:text-brand-900 dark:text-slate-200 dark:hover:text-white" href="/auth/login">
          Login
        </Link>
      </p>
    </section>
  );
}
