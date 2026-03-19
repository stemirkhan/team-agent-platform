"use client";

import { CheckSquare, KeyRound, Mail, ShieldCheck, UserRound, UsersRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { bootstrapPlatform, setAccessToken } from "@/lib/auth-client";
import { t, type Locale } from "@/lib/i18n";

type BootstrapSetupFormProps = {
  locale: Locale;
  initialAllowOpenRegistration: boolean;
};

export function BootstrapSetupForm({
  locale,
  initialAllowOpenRegistration,
}: BootstrapSetupFormProps) {
  const router = useRouter();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [allowOpenRegistration, setAllowOpenRegistration] = useState(
    initialAllowOpenRegistration
  );
  const [seedStarterTeam, setSeedStarterTeam] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setErrorMessage(null);

    try {
      const result = await bootstrapPlatform(
        {
          display_name: displayName.trim(),
          email: email.trim(),
          password,
          allow_open_registration: allowOpenRegistration,
          seed_starter_team: seedStarterTeam,
        },
        {
          fallbackMessage: t(locale, {
            ru: "Не удалось завершить первичную настройку платформы.",
            en: "Failed to complete initial platform setup.",
          }),
        }
      );

      setAccessToken(result.access_token);
      router.push(
        result.seeded_team_slug ? `/teams/${result.seeded_team_slug}` : "/runs"
      );
      router.refresh();
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : t(locale, {
              ru: "Не удалось завершить первичную настройку платформы.",
              en: "Failed to complete initial platform setup.",
            })
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="mx-auto max-w-3xl rounded-3xl border border-slate-200 bg-white p-6 shadow-lg shadow-slate-200/60 dark:border-zinc-700 dark:bg-zinc-900/95">
      <p className="mb-3 inline-flex items-center gap-2 rounded-full bg-brand-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-brand-800">
        <ShieldCheck className="h-3.5 w-3.5" />
        {t(locale, { ru: "First Run Setup", en: "First Run Setup" })}
      </p>
      <h1 className="mb-2 text-2xl font-black text-slate-900 dark:text-slate-50">
        {t(locale, {
          ru: "Первичная настройка платформы",
          en: "Initial platform setup",
        })}
      </h1>
      <p className="mb-6 text-sm text-slate-600 dark:text-slate-300">
        {t(locale, {
          ru: "Создайте первого администратора, задайте политику self-registration и решите, нужен ли стартовый fullstack squad прямо после установки.",
          en: "Create the first admin, choose the self-registration policy, and decide whether to add the starter fullstack squad right after installation.",
        })}
      </p>

      <form className="space-y-5" onSubmit={onSubmit}>
        <div className="grid gap-4 md:grid-cols-2">
          <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
            {t(locale, { ru: "Имя администратора", en: "Admin display name" })}
            <div className="relative mt-1">
              <input
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 pr-10 text-sm outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-200 dark:border-zinc-600 dark:bg-zinc-900"
                onChange={(event) => setDisplayName(event.target.value)}
                placeholder={t(locale, { ru: "Platform Owner", en: "Platform Owner" })}
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
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 pr-10 text-sm outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-200 dark:border-zinc-600 dark:bg-zinc-900"
                onChange={(event) => setEmail(event.target.value)}
                placeholder="owner@example.com"
                required
                type="email"
                value={email}
              />
              <Mail className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            </div>
          </label>
        </div>

        <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
          {t(locale, { ru: "Пароль", en: "Password" })}
          <div className="relative mt-1">
            <input
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 pr-10 text-sm outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-200 dark:border-zinc-600 dark:bg-zinc-900"
              minLength={8}
              onChange={(event) => setPassword(event.target.value)}
              placeholder={t(locale, { ru: "Минимум 8 символов", en: "At least 8 characters" })}
              required
              type="password"
              value={password}
            />
            <KeyRound className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          </div>
        </label>

        <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50/80 p-4 dark:border-zinc-800 dark:bg-zinc-900/70">
          <label className="flex items-start gap-3 text-sm text-slate-700 dark:text-slate-200">
            <input
              checked={allowOpenRegistration}
              className="mt-1"
              onChange={(event) => setAllowOpenRegistration(event.target.checked)}
              type="checkbox"
            />
            <span>
              <span className="block font-semibold">
                {t(locale, {
                  ru: "Разрешить self-registration после setup",
                  en: "Allow self-registration after setup",
                })}
              </span>
              <span className="mt-1 block text-slate-500 dark:text-slate-400">
                {t(locale, {
                  ru: "Если выключить, публичная регистрация через `/auth/register` сразу закроется после создания первого admin.",
                  en: "If disabled, public registration through `/auth/register` closes immediately after the first admin is created.",
                })}
              </span>
            </span>
          </label>

          <label className="flex items-start gap-3 text-sm text-slate-700 dark:text-slate-200">
            <input
              checked={seedStarterTeam}
              className="mt-1"
              onChange={(event) => setSeedStarterTeam(event.target.checked)}
              type="checkbox"
            />
            <span>
              <span className="block font-semibold">
                {t(locale, {
                  ru: "Добавить стартовую команду Fullstack Delivery Squad",
                  en: "Add the Fullstack Delivery Squad starter team",
                })}
              </span>
              <span className="mt-1 block text-slate-500 dark:text-slate-400">
                {t(locale, {
                  ru: "Будут созданы 3 опубликованных агента: orchestration, backend и frontend, плюс готовая published-команда для старта.",
                  en: "This creates 3 published starter agents for orchestration, backend, and frontend plus one ready-to-use published team.",
                })}
              </span>
            </span>
          </label>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-slate-100">
              <ShieldCheck className="h-4 w-4 text-slate-500 dark:text-slate-400" />
              {t(locale, { ru: "Что создается", en: "What gets created" })}
            </div>
            <ul className="mt-3 space-y-2 text-sm text-slate-600 dark:text-slate-300">
              <li>{t(locale, { ru: "Первый пользователь с ролью admin", en: "The first user with admin role" })}</li>
              <li>{t(locale, { ru: "Начальная политика регистрации", en: "The initial registration policy" })}</li>
              <li>{t(locale, { ru: "Опциональный starter squad", en: "An optional starter squad" })}</li>
            </ul>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-slate-100">
              <UsersRound className="h-4 w-4 text-slate-500 dark:text-slate-400" />
              {t(locale, { ru: "Стартовый squad", en: "Starter squad" })}
            </div>
            <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
              {t(locale, {
                ru: "Если опцию включить, после setup появится команда `Fullstack Delivery Squad` и базовые published-профили для backend, frontend и orchestration.",
                en: "If enabled, setup seeds the `Fullstack Delivery Squad` team and starter published profiles for backend, frontend, and orchestration.",
              })}
            </p>
          </div>
        </div>

        {errorMessage ? (
          <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {errorMessage}
          </p>
        ) : null}

        <Button disabled={submitting} type="submit">
          <CheckSquare className="mr-2 h-4 w-4" />
          {submitting
            ? t(locale, { ru: "Завершаем настройку...", en: "Completing setup..." })
            : t(locale, { ru: "Завершить первичную настройку", en: "Complete initial setup" })}
        </Button>
      </form>
    </section>
  );
}
