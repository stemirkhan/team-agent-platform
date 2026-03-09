"use client";

import Link from "next/link";
import { Download } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { clearAccessToken, fetchCurrentUser, getAccessToken, type AuthUser } from "@/lib/auth-client";
import {
  type CodexReasoningEffort,
  type CodexSandboxMode,
  createAgentExport,
  createTeamExport,
  resolveDownloadUrl,
} from "@/lib/api";
import { formatAuthLoading, t, type Locale } from "@/lib/i18n";

type ExportControlsProps = {
  entityType: "agent" | "team";
  slug: string;
  status: "draft" | "published" | "archived" | "hidden";
  locale: Locale;
};

export function ExportControls({
  entityType,
  slug,
  status,
  locale,
}: ExportControlsProps) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loadingAuth, setLoadingAuth] = useState(true);

  const [submitting, setSubmitting] = useState(false);
  const [lastDownloadUrl, setLastDownloadUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [codexModel, setCodexModel] = useState("");
  const [codexReasoningEffort, setCodexReasoningEffort] = useState<CodexReasoningEffort>("medium");
  const [codexSandboxMode, setCodexSandboxMode] = useState<CodexSandboxMode>("read-only");

  useEffect(() => {
    let cancelled = false;

    async function resolveUser() {
      const currentToken = getAccessToken();
      if (!currentToken) {
        if (!cancelled) {
          setUser(null);
          setToken(null);
          setLoadingAuth(false);
        }
        return;
      }

      try {
        const currentUser = await fetchCurrentUser(currentToken);
        if (!cancelled) {
          setUser(currentUser);
          setToken(currentToken);
          setLoadingAuth(false);
        }
      } catch {
        clearAccessToken();
        if (!cancelled) {
          setUser(null);
          setToken(null);
          setLoadingAuth(false);
        }
      }
    }

    void resolveUser();

    return () => {
      cancelled = true;
    };
  }, [entityType, slug]);

  async function onExport(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!token) {
      router.push("/auth/login");
      return;
    }

    setSubmitting(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    setLastDownloadUrl(null);

    try {
      const payload = {
        runtime_target: "codex" as const,
        codex: {
          model: codexModel.trim() || undefined,
          model_reasoning_effort: codexReasoningEffort,
          sandbox_mode: codexSandboxMode,
        },
      };
      const created =
        entityType === "agent"
          ? await createAgentExport(slug, payload, token)
          : await createTeamExport(slug, payload, token);
      if (!created.result_url) {
        throw new Error(
          t(locale, {
            ru: "Экспорт завершился без ссылки на артефакт.",
            en: "Export completed without artifact URL.",
          })
        );
      }

      const downloadUrl = resolveDownloadUrl(created.result_url);
      setLastDownloadUrl(downloadUrl);
      setSuccessMessage(
        t(locale, { ru: "Экспорт готов. Скачивание началось.", en: "Export ready. Download started." })
      );

      if (typeof window !== "undefined") {
        const anchor = window.document.createElement("a");
        anchor.href = downloadUrl;
        anchor.target = "_blank";
        anchor.rel = "noopener noreferrer";
        window.document.body.appendChild(anchor);
        anchor.click();
        window.document.body.removeChild(anchor);
      }
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : t(locale, { ru: "Не удалось создать экспорт.", en: "Failed to create export." })
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (loadingAuth) {
    return (
      <section className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
        <p className="text-sm text-slate-500 dark:text-slate-400">{formatAuthLoading(locale)}</p>
      </section>
    );
  }

  if (!user) {
    return (
      <section className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
        <h2 className="mb-2 text-xl font-bold text-slate-900 dark:text-slate-50">
          {t(locale, { ru: "Экспорт", en: "Export" })}
        </h2>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          {t(locale, {
            ru: `Войдите, чтобы экспортировать ${entityType === "agent" ? "агента" : "команду"} в Codex.`,
            en: `Login to export this ${entityType} to Codex.`,
          })}
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-50">
            {t(locale, { ru: "Экспорт", en: "Export" })}
          </h2>
          <p className="text-sm text-slate-600 dark:text-slate-300">
            {t(locale, { ru: "Вы вошли как", en: "Signed in as" })} {user.display_name}
          </p>
        </div>
      </div>

      <form className="space-y-3" onSubmit={onExport}>
        {status !== "published" ? (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200">
            {t(locale, {
              ru: "Экспорт доступен только для опубликованных сущностей.",
              en: "Export is available only for published entities.",
            })}
          </div>
        ) : null}

        <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 dark:border-zinc-800 dark:bg-zinc-900/70">
          <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            {t(locale, { ru: "Параметры скачивания", en: "Download parameters" })}
          </p>

          <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 dark:border-zinc-800 dark:bg-zinc-950 dark:text-slate-200">
            Codex
          </div>

          <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
            {t(locale, { ru: "Модель", en: "Model" })}
            <input
              className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              onChange={(event) => setCodexModel(event.target.value)}
              placeholder={t(locale, {
                ru: "Оставь пустым для модели аккаунта",
                en: "Leave empty to use the account default",
              })}
              value={codexModel}
            />
            <span className="mt-1 block text-xs font-normal text-slate-500 dark:text-slate-400">
              {t(locale, {
                ru: "Если модель не указана, Codex CLI сам выберет поддерживаемую модель из локального аккаунта.",
                en: "If model is omitted, Codex CLI will use a supported model from the local account.",
              })}
            </span>
          </label>

          <div className="grid gap-3 md:grid-cols-2">
            <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
              {t(locale, { ru: "Уровень reasoning", en: "Reasoning effort" })}
              <select
                className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                onChange={(event) => setCodexReasoningEffort(event.target.value as CodexReasoningEffort)}
                value={codexReasoningEffort}
              >
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
              </select>
            </label>

            <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
              {t(locale, { ru: "Режим sandbox", en: "Sandbox mode" })}
              <select
                className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                onChange={(event) => setCodexSandboxMode(event.target.value as CodexSandboxMode)}
                value={codexSandboxMode}
              >
                <option value="read-only">read-only</option>
                <option value="workspace-write">workspace-write</option>
                <option value="danger-full-access">danger-full-access</option>
              </select>
            </label>
          </div>
        </div>

        {errorMessage ? (
          <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {errorMessage}
          </p>
        ) : null}

        {successMessage ? (
          <div className="space-y-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            <p>{successMessage}</p>
            {lastDownloadUrl ? (
              <Link
                className="inline-flex items-center gap-2 font-semibold hover:underline"
                href={lastDownloadUrl}
                rel="noreferrer"
                target="_blank"
              >
                <Download className="h-4 w-4" />
                {t(locale, { ru: "Открыть артефакт", en: "Open artifact" })}
              </Link>
            ) : null}
          </div>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <Button disabled={submitting || status !== "published"} type="submit">
            {submitting
              ? t(locale, { ru: "Готовим экспорт...", en: "Preparing export..." })
              : t(locale, { ru: "Экспортировать для Codex", en: "Export for Codex" })}
          </Button>
          {lastDownloadUrl ? (
            <a
              className="inline-flex h-10 items-center justify-center rounded-xl bg-white px-4 text-sm font-semibold text-slate-800 ring-1 ring-slate-300 transition hover:bg-slate-50 hover:ring-slate-400 dark:bg-zinc-900 dark:text-slate-100 dark:ring-zinc-700 dark:hover:bg-zinc-800 dark:hover:ring-zinc-600"
              href={lastDownloadUrl}
              rel="noreferrer"
              target="_blank"
            >
              <Download className="mr-2 h-4 w-4" />
              {t(locale, { ru: "Скачать снова", en: "Download again" })}
            </a>
          ) : null}
        </div>
      </form>
    </section>
  );
}
