"use client";

import Link from "next/link";
import { Download } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { clearAccessToken, fetchCurrentUser, getAccessToken, type AuthUser } from "@/lib/auth-client";
import {
  type ClaudeModel,
  type ClaudePermissionMode,
  type CodexReasoningEffort,
  type CodexSandboxMode,
  type OpenCodePermission,
  createAgentExport,
  createTeamExport,
  resolveDownloadUrl,
  type RuntimeTarget,
} from "@/lib/api";
import { formatAuthLoading, t, type Locale } from "@/lib/i18n";

type ExportControlsProps = {
  entityType: "agent" | "team";
  slug: string;
  status: "draft" | "published" | "archived" | "hidden";
  locale: Locale;
};

const runtimeOptions: Array<{ value: RuntimeTarget; label: string }> = [
  { value: "codex", label: "Codex" },
  { value: "claude_code", label: "Claude Code" },
  { value: "opencode", label: "OpenCode" },
];

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

  const [runtimeTarget, setRuntimeTarget] = useState<RuntimeTarget>("codex");
  const [submitting, setSubmitting] = useState(false);
  const [lastDownloadUrl, setLastDownloadUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [codexModel, setCodexModel] = useState("gpt-5.3-codex-spark");
  const [codexReasoningEffort, setCodexReasoningEffort] = useState<CodexReasoningEffort>("medium");
  const [codexSandboxMode, setCodexSandboxMode] = useState<CodexSandboxMode>("read-only");
  const [claudeModel, setClaudeModel] = useState<ClaudeModel>("inherit");
  const [claudePermissionMode, setClaudePermissionMode] = useState<ClaudePermissionMode>("default");
  const [opencodeModel, setOpencodeModel] = useState("");
  const [opencodePermission, setOpencodePermission] = useState<OpenCodePermission>("ask");

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
      const exportPayload =
        runtimeTarget === "codex"
          ? {
              runtime_target: runtimeTarget,
              codex: {
                model: codexModel.trim() || undefined,
                model_reasoning_effort: codexReasoningEffort,
                sandbox_mode: codexSandboxMode,
              },
            }
          : {
              runtime_target: runtimeTarget,
              claude: {
                model: claudeModel,
                permissionMode: claudePermissionMode,
              },
            };
      const finalExportPayload =
        runtimeTarget === "opencode"
          ? {
              runtime_target: runtimeTarget,
              opencode: {
                model: opencodeModel.trim() || undefined,
                permission: opencodePermission,
              },
            }
          : exportPayload;
      const created =
        entityType === "agent"
          ? await createAgentExport(slug, finalExportPayload, token)
          : await createTeamExport(slug, finalExportPayload, token);
      if (!created.result_url) {
        throw new Error(t(locale, { ru: "Экспорт завершился без ссылки на артефакт.", en: "Export completed without artifact URL." }));
      }

      const downloadUrl = resolveDownloadUrl(created.result_url);
      setLastDownloadUrl(downloadUrl);
      setSuccessMessage(t(locale, { ru: "Экспорт готов. Скачивание началось.", en: "Export ready. Download started." }));

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
        <h2 className="mb-2 text-xl font-bold text-slate-900 dark:text-slate-50">{t(locale, { ru: "Экспорт", en: "Export" })}</h2>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          {t(locale, {
            ru: `Войдите, чтобы экспортировать ${entityType === "agent" ? "агента" : "команду"} в Codex, Claude Code или OpenCode.`,
            en: `Login to export this ${entityType} to Codex, Claude Code, or OpenCode.`
          })}
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-50">{t(locale, { ru: "Экспорт", en: "Export" })}</h2>
          <p className="text-sm text-slate-600 dark:text-slate-300">{t(locale, { ru: "Вы вошли как", en: "Signed in as" })} {user.display_name}</p>
        </div>
      </div>

      <form className="space-y-3" onSubmit={onExport}>
        <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 dark:border-zinc-800 dark:bg-zinc-900/70">
          <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            {t(locale, { ru: "Параметры скачивания", en: "Download parameters" })}
          </p>

          <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
            {t(locale, { ru: "Целевой runtime", en: "Runtime target" })}
            <select
              className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              onChange={(event) => setRuntimeTarget(event.target.value as RuntimeTarget)}
              value={runtimeTarget}
            >
              {runtimeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          {runtimeTarget === "codex" ? (
            <>
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t(locale, { ru: "Модель", en: "Model" })}
                <input
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  onChange={(event) => setCodexModel(event.target.value)}
                  placeholder="gpt-5.3-codex-spark"
                  value={codexModel}
                />
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
            </>
          ) : runtimeTarget === "claude_code" ? (
            <div className="grid gap-3 md:grid-cols-2">
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t(locale, { ru: "Модель", en: "Model" })}
                <select
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  onChange={(event) => setClaudeModel(event.target.value as ClaudeModel)}
                  value={claudeModel}
                >
                  <option value="inherit">inherit</option>
                  <option value="sonnet">sonnet</option>
                  <option value="opus">opus</option>
                  <option value="haiku">haiku</option>
                </select>
              </label>

              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t(locale, { ru: "Режим разрешений", en: "Permission mode" })}
                <select
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  onChange={(event) => setClaudePermissionMode(event.target.value as ClaudePermissionMode)}
                  value={claudePermissionMode}
                >
                  <option value="default">default</option>
                  <option value="acceptEdits">acceptEdits</option>
                  <option value="dontAsk">dontAsk</option>
                  <option value="bypassPermissions">bypassPermissions</option>
                  <option value="plan">plan</option>
                </select>
              </label>
            </div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t(locale, { ru: "Модель", en: "Model" })}
                <input
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  onChange={(event) => setOpencodeModel(event.target.value)}
                  placeholder="provider/model-id"
                  value={opencodeModel}
                />
              </label>

              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                {t(locale, { ru: "Разрешение", en: "Permission" })}
                <select
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  onChange={(event) => setOpencodePermission(event.target.value as OpenCodePermission)}
                  value={opencodePermission}
                >
                  <option value="ask">ask</option>
                  <option value="allow">allow</option>
                  <option value="deny">deny</option>
                </select>
              </label>
            </div>
          )}
        </div>

        {status !== "published" ? (
          <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
            {t(locale, {
              ru: `Экспортировать можно только опубликованные ${entityType === "agent" ? "агенты" : "команды"}.`,
              en: `Only published ${entityType}s can be exported.`
            })}
          </p>
        ) : null}

        {errorMessage ? (
          <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {errorMessage}
          </p>
        ) : null}

        {successMessage ? (
          <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {successMessage}
          </p>
        ) : null}

        {lastDownloadUrl ? (
          <p className="break-all rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:border-zinc-800 dark:bg-zinc-900/70 dark:text-slate-200">
            {t(locale, { ru: "Если скачивание не началось, используйте эту ссылку:", en: "If download did not start, use this link:" })}{" "}
            <a
              className="font-semibold text-brand-700 hover:text-brand-900 dark:text-slate-200 dark:hover:text-white"
              href={lastDownloadUrl}
              rel="noreferrer"
              target="_blank"
            >
              {t(locale, { ru: "Скачать артефакт", en: "Download artifact" })}
            </a>
          </p>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <Button disabled={submitting || status !== "published"} type="submit">
            <Download className="mr-2 h-4 w-4" />
            {submitting
              ? t(locale, { ru: "Экспортируем...", en: "Exporting..." })
              : t(locale, { ru: "Экспортировать и скачать", en: "Export & Download" })}
          </Button>
        </div>
      </form>
    </section>
  );
}
