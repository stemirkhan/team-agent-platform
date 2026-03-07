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
  createAgentVersion,
  createTeamExport,
  resolveDownloadUrl,
  type RuntimeTarget,
} from "@/lib/api";

type ExportControlsProps = {
  entityType: "agent" | "team";
  slug: string;
  status: "draft" | "published" | "archived" | "hidden";
  agentTitle?: string;
  agentShortDescription?: string;
};

const runtimeOptions: Array<{ value: RuntimeTarget; label: string }> = [
  { value: "codex", label: "Codex" },
  { value: "claude_code", label: "Claude Code" },
  { value: "opencode", label: "OpenCode" },
];

function extractMissingVersionAgentSlug(message: string | null): string | null {
  if (!message) {
    return null;
  }
  const match = message.match(/Agent '([^']+)' has no versions for export\./);
  return match ? match[1] : null;
}

export function ExportControls({
  entityType,
  slug,
  status,
  agentTitle,
  agentShortDescription,
}: ExportControlsProps) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loadingAuth, setLoadingAuth] = useState(true);

  const [runtimeTarget, setRuntimeTarget] = useState<RuntimeTarget>("codex");
  const [submitting, setSubmitting] = useState(false);
  const [creatingVersion, setCreatingVersion] = useState(false);
  const [lastDownloadUrl, setLastDownloadUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [initialVersion, setInitialVersion] = useState("0.1.0");
  const [codexModel, setCodexModel] = useState("gpt-5.3-codex-spark");
  const [codexReasoningEffort, setCodexReasoningEffort] = useState<CodexReasoningEffort>("medium");
  const [codexSandboxMode, setCodexSandboxMode] = useState<CodexSandboxMode>("read-only");
  const [claudeModel, setClaudeModel] = useState<ClaudeModel>("inherit");
  const [claudePermissionMode, setClaudePermissionMode] = useState<ClaudePermissionMode>("default");
  const [opencodeModel, setOpencodeModel] = useState("");
  const [opencodePermission, setOpencodePermission] = useState<OpenCodePermission>("ask");
  const [agentInstructions, setAgentInstructions] = useState(
    "Review repository context and execute requested workflow with available tools.",
  );

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
        throw new Error("Export completed without artifact URL.");
      }

      const downloadUrl = resolveDownloadUrl(created.result_url);
      setLastDownloadUrl(downloadUrl);
      setSuccessMessage("Export ready. Download started.");

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
      setErrorMessage(error instanceof Error ? error.message : "Failed to create export.");
    } finally {
      setSubmitting(false);
    }
  }

  async function onCreateInitialVersion() {
    if (!token) {
      router.push("/auth/login");
      return;
    }

    setCreatingVersion(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      await createAgentVersion(
        slug,
        {
          version: initialVersion.trim() || "0.1.0",
          changelog: "Initial release for runtime export compatibility.",
          manifest_json: {
            title: agentTitle ?? slug,
            description: agentShortDescription ?? "Initial generated version.",
            instructions: agentInstructions.trim(),
            codex: {
              description: agentShortDescription ?? agentTitle ?? slug,
              developer_instructions: agentInstructions.trim(),
            },
            claude: {
              description: agentShortDescription ?? agentTitle ?? slug,
              prompt: agentInstructions.trim(),
            },
            opencode: {
              description: agentShortDescription ?? agentTitle ?? slug,
              prompt: agentInstructions.trim(),
            },
          },
          export_targets: ["codex", "claude_code", "opencode"],
          compatibility_matrix: { codex: true, claude_code: true, opencode: true },
          install_instructions: "Use this version for runtime export.",
        },
        token,
      );
      setSuccessMessage("Initial version created. You can export now.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to create initial version.");
    } finally {
      setCreatingVersion(false);
    }
  }

  const missingVersionAgentSlug = extractMissingVersionAgentSlug(errorMessage);
  const canCreateInitialVersion = entityType === "agent" && missingVersionAgentSlug === slug && status === "published";

  if (loadingAuth) {
    return (
      <section className="rounded-2xl border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-5">
        <p className="text-sm text-slate-500 dark:text-slate-400">Checking authorization...</p>
      </section>
    );
  }

  if (!user) {
    return (
      <section className="rounded-2xl border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-5">
        <h2 className="mb-2 text-xl font-bold text-slate-900 dark:text-slate-50">Export</h2>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          Login to export this {entityType} to Codex, Claude Code, or OpenCode.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-50">Export</h2>
          <p className="text-sm text-slate-600 dark:text-slate-300">Signed in as {user.display_name}</p>
        </div>
      </div>

      <form className="space-y-3" onSubmit={onExport}>
        <div className="space-y-3 rounded-lg border border-slate-200 dark:border-zinc-700 bg-slate-50 dark:bg-zinc-800/70 px-3 py-3">
          <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            Download parameters
          </p>

          <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
            Runtime target
            <select
              className="mt-1 w-full rounded-lg border border-slate-300 dark:border-zinc-600 px-3 py-2 text-sm"
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
                Model
                <input
                  className="mt-1 w-full rounded-lg border border-slate-300 dark:border-zinc-600 px-3 py-2 text-sm"
                  onChange={(event) => setCodexModel(event.target.value)}
                  placeholder="gpt-5.3-codex-spark"
                  value={codexModel}
                />
              </label>

              <div className="grid gap-3 md:grid-cols-2">
                <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                  Reasoning effort
                  <select
                    className="mt-1 w-full rounded-lg border border-slate-300 dark:border-zinc-600 px-3 py-2 text-sm"
                    onChange={(event) => setCodexReasoningEffort(event.target.value as CodexReasoningEffort)}
                    value={codexReasoningEffort}
                  >
                    <option value="low">low</option>
                    <option value="medium">medium</option>
                    <option value="high">high</option>
                  </select>
                </label>

                <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                  Sandbox mode
                  <select
                    className="mt-1 w-full rounded-lg border border-slate-300 dark:border-zinc-600 px-3 py-2 text-sm"
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
                Model
                <select
                  className="mt-1 w-full rounded-lg border border-slate-300 dark:border-zinc-600 px-3 py-2 text-sm"
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
                Permission mode
                <select
                  className="mt-1 w-full rounded-lg border border-slate-300 dark:border-zinc-600 px-3 py-2 text-sm"
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
                Model
                <input
                  className="mt-1 w-full rounded-lg border border-slate-300 dark:border-zinc-600 px-3 py-2 text-sm"
                  onChange={(event) => setOpencodeModel(event.target.value)}
                  placeholder="provider/model-id"
                  value={opencodeModel}
                />
              </label>

              <label className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
                Permission
                <select
                  className="mt-1 w-full rounded-lg border border-slate-300 dark:border-zinc-600 px-3 py-2 text-sm"
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
            Only published {entityType}s can be exported.
          </p>
        ) : null}

        {errorMessage ? (
          <div className="space-y-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            <p>{errorMessage}</p>

            {canCreateInitialVersion ? (
              <div className="space-y-3 rounded-lg border border-slate-200 bg-white/80 px-3 py-3 text-slate-800">
                <p className="text-sm font-semibold">Create initial export version</p>

                <label className="block text-sm font-semibold text-slate-700">
                  Version
                  <input
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    onChange={(event) => setInitialVersion(event.target.value)}
                    placeholder="0.1.0"
                    value={initialVersion}
                  />
                </label>

                <label className="block text-sm font-semibold text-slate-700">
                  Instructions
                  <textarea
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    onChange={(event) => setAgentInstructions(event.target.value)}
                    placeholder="Instructions for exported agent behavior"
                    rows={4}
                    value={agentInstructions}
                  />
                </label>

                <Button disabled={creatingVersion} onClick={onCreateInitialVersion} type="button" variant="secondary">
                  {creatingVersion ? "Creating version..." : "Create initial version"}
                </Button>
              </div>
            ) : null}

            {entityType === "team" && missingVersionAgentSlug ? (
              <p>
                Open agent page and create version:{" "}
                <Link className="font-semibold underline" href={`/agents/${missingVersionAgentSlug}`}>
                  /agents/{missingVersionAgentSlug}
                </Link>
              </p>
            ) : null}
          </div>
        ) : null}

        {successMessage ? (
          <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {successMessage}
          </p>
        ) : null}

        {lastDownloadUrl ? (
          <p className="rounded-lg border border-slate-200 dark:border-zinc-700 bg-slate-50 dark:bg-zinc-800/70 px-3 py-2 text-sm text-slate-700 dark:text-slate-200 break-all">
            If download did not start, use this link:{" "}
            <a
              className="font-semibold text-brand-700 hover:text-brand-900 dark:text-slate-200 dark:hover:text-white"
              href={lastDownloadUrl}
              rel="noreferrer"
              target="_blank"
            >
              Download artifact
            </a>
          </p>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <Button disabled={submitting || status !== "published"} type="submit">
            <Download className="mr-2 h-4 w-4" />
            {submitting ? "Exporting..." : "Export & Download"}
          </Button>
        </div>
      </form>
    </section>
  );
}
