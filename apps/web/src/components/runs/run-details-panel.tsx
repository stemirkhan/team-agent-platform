"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  Activity,
  Clock3,
  ExternalLink,
  FolderGit2,
  GitBranch,
  Loader2,
  PlaySquare,
  RefreshCcw,
  RotateCcw,
  ScrollText,
  ShieldCheck,
  Square,
  SquareTerminal
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { RunReportPanel } from "@/components/runs/run-report-panel";
import { RunStatusBadge } from "@/components/runs/run-status-badge";
import { RunTerminalPanel } from "@/components/runs/run-terminal-panel";
import { Button } from "@/components/ui/button";
import { LocalizedTimestamp } from "@/components/ui/localized-timestamp";
import {
  clearAccessToken,
  fetchCurrentUser,
  getAccessToken,
  type AuthUser
} from "@/lib/auth-client";
import {
  cancelRun,
  fetchRunTerminalSession,
  fetchRun,
  fetchRunEvents,
  fetchWorkspace,
  resumeRun,
  type CodexSessionRead,
  type Run,
  type RunEvent,
  type Workspace
} from "@/lib/api";
import { formatAuthLoading, t, type Locale } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type RunDetailsPanelProps = {
  locale: Locale;
  runId: string;
};

type RunPageTabId = "overview" | "activity" | "report" | "terminal";

const runPageTabs = ["overview", "activity", "report", "terminal"] as const satisfies ReadonlyArray<RunPageTabId>;

const terminalStatuses = new Set<Run["status"]>(["completed", "interrupted", "failed", "cancelled"]);

function parseRunPageTab(value: string | null): RunPageTabId {
  if (value && runPageTabs.includes(value as RunPageTabId)) {
    return value as RunPageTabId;
  }
  return "overview";
}

function isTemporaryExecutionPath(path: string): boolean {
  return path === "TASK.md" || path === ".codex" || path.startsWith(".codex/") || path.startsWith("agents/");
}

function formatShortSha(value: string | null): string {
  if (!value) {
    return "-";
  }
  return value.slice(0, 7);
}

function formatWorkspaceStatus(locale: Locale, value: Workspace["status"]): string {
  switch (value) {
    case "prepared":
      return t(locale, { ru: "prepared", en: "prepared" });
    case "committed":
      return t(locale, { ru: "committed", en: "committed" });
    case "pushed":
      return t(locale, { ru: "pushed", en: "pushed" });
    case "pull_request_created":
      return t(locale, { ru: "pull request created", en: "pull request created" });
    default:
      return String(value).replaceAll("_", " ");
  }
}

function parseTimestamp(value: string | null): number | null {
  if (!value) {
    return null;
  }

  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function formatRunDuration(
  locale: Locale,
  startedAt: string | null,
  finishedAt: string | null,
  nowMs: number
): string {
  const startedAtMs = parseTimestamp(startedAt);
  if (startedAtMs === null) {
    return t(locale, { ru: "ожидает старта", en: "waiting to start" });
  }

  const finishedAtMs = parseTimestamp(finishedAt);
  const end = finishedAtMs ?? nowMs;
  const totalSeconds = Math.max(0, Math.floor((end - startedAtMs) / 1000));

  const days = Math.floor(totalSeconds / 86_400);
  const hours = Math.floor((totalSeconds % 86_400) / 3_600);
  const minutes = Math.floor((totalSeconds % 3_600) / 60);
  const seconds = totalSeconds % 60;

  const labels =
    locale === "ru"
      ? { day: "д", hour: "ч", minute: "м", second: "с" }
      : { day: "d", hour: "h", minute: "m", second: "s" };

  const parts: string[] = [];
  if (days > 0) {
    parts.push(`${days}${labels.day}`);
  }
  if (hours > 0) {
    parts.push(`${hours}${labels.hour}`);
  }
  if (minutes > 0) {
    parts.push(`${minutes}${labels.minute}`);
  }
  if (seconds > 0 || parts.length === 0) {
    parts.push(`${seconds}${labels.second}`);
  }

  return parts.slice(0, 3).join(" ");
}

function formatCompactNumber(locale: Locale, value: number | null): string {
  if (value === null) {
    return "-";
  }

  return new Intl.NumberFormat(locale === "ru" ? "ru-RU" : "en-US").format(value);
}

function formatAbbreviatedNumber(locale: Locale, value: number | null): string {
  if (value === null) {
    return "-";
  }

  const formatter = new Intl.NumberFormat(locale === "ru" ? "ru-RU" : "en-US", {
    notation: "compact",
    maximumFractionDigits: 1
  });
  return formatter.format(value);
}

function extractEventMessage(event: RunEvent, locale: Locale): string {
  const payload = event.payload_json;
  if (payload && typeof payload.message === "string" && payload.message.length > 0) {
    return payload.message;
  }
  if (payload && typeof payload.detail === "string" && payload.detail.length > 0) {
    return payload.detail;
  }

  switch (event.event_type) {
    case "status":
      return t(locale, { ru: "Изменение статуса run.", en: "Run status transition." });
    case "error":
      return t(locale, { ru: "Ошибка выполнения run.", en: "Run execution error." });
    case "note":
      return t(locale, { ru: "Служебная заметка run.", en: "Run note." });
    default:
      return event.event_type;
  }
}

function readStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

type TraceSpawnedAgent = {
  thread_id: string;
  role: string | null;
  status: string | null;
  result_preview: string | null;
};

function readSpawnedAgents(value: unknown): TraceSpawnedAgent[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.flatMap((item) => {
    if (!item || typeof item !== "object") {
      return [];
    }

    const payload = item as Record<string, unknown>;
    const threadId = typeof payload.thread_id === "string" ? payload.thread_id.trim() : "";
    if (!threadId) {
      return [];
    }

    const role =
      typeof payload.role === "string" && payload.role.trim().length > 0
        ? payload.role.trim()
        : null;
    const status =
      typeof payload.status === "string" && payload.status.trim().length > 0
        ? payload.status.trim()
        : null;
    const resultPreview =
      typeof payload.result_preview === "string" && payload.result_preview.trim().length > 0
        ? payload.result_preview.trim()
        : null;

    return [{ thread_id: threadId, role, status, result_preview: resultPreview }];
  });
}

function renderEventAuditDetails(event: RunEvent, locale: Locale): JSX.Element | null {
  const payload = event.payload_json;
  if (!payload || typeof payload.kind !== "string") {
    return null;
  }

  if (payload.kind === "codex_bundle") {
    const configuredAgents = readStringArray(payload.configured_agents);
    const multiAgentEnabled = payload.multi_agent_enabled === true;

    return (
      <div className="mt-3 space-y-3 rounded-2xl border border-slate-200 bg-white/80 p-3 dark:border-zinc-700 dark:bg-zinc-950/70">
        <div className="flex flex-wrap gap-2">
          <span className="rounded-full bg-slate-200 px-3 py-1 text-xs font-semibold text-slate-700 dark:bg-zinc-800 dark:text-slate-300">
            {multiAgentEnabled
              ? t(locale, { ru: "multi-agent requested", en: "multi-agent requested" })
              : t(locale, { ru: "standard codex bundle", en: "standard codex bundle" })}
          </span>
          {configuredAgents.map((agent) => (
            <span
              className="rounded-full bg-sky-100 px-3 py-1 text-xs font-semibold text-sky-800 dark:bg-sky-500/15 dark:text-sky-200"
              key={agent}
            >
              {agent}
            </span>
          ))}
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {t(locale, {
            ru: "Снимок materialized `.codex` bundle сохранён в run event до cleanup.",
            en: "The materialized `.codex` bundle snapshot was stored in the run event before cleanup."
          })}
        </p>
      </div>
    );
  }

  if (payload.kind === "codex_execution_trace") {
    const skillRefs = readStringArray(payload.skill_refs);
    const agentConfigReads = readStringArray(payload.agent_config_reads);
    const delegationMarkers = readStringArray(payload.delegation_markers);
    const additionalThreadIds = readStringArray(payload.additional_thread_ids);
    const spawnedAgents = readSpawnedAgents(payload.spawned_agents);
    const traceCaptureError =
      typeof payload.trace_capture_error === "string" ? payload.trace_capture_error : null;
    const signalLevel =
      typeof payload.multi_agent_signal_level === "string" ? payload.multi_agent_signal_level : "none";

    return (
      <div className="mt-3 space-y-3 rounded-2xl border border-slate-200 bg-white/80 p-3 dark:border-zinc-700 dark:bg-zinc-950/70">
        {traceCaptureError ? (
          <p className="text-xs text-rose-600 dark:text-rose-300">{traceCaptureError}</p>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <span
            className={
              signalLevel === "confirmed"
                ? "rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-200"
                : signalLevel === "possible"
                  ? "rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800 dark:bg-amber-500/15 dark:text-amber-200"
                  : "rounded-full bg-slate-200 px-3 py-1 text-xs font-semibold text-slate-700 dark:bg-zinc-800 dark:text-slate-300"
            }
          >
            {signalLevel === "confirmed"
              ? t(locale, { ru: "sub-agent confirmed", en: "sub-agent confirmed" })
              : signalLevel === "possible"
                ? t(locale, { ru: "sub-agent possible", en: "sub-agent possible" })
                : t(locale, { ru: "no sub-agent signal", en: "no sub-agent signal" })}
          </span>
        </div>

        {spawnedAgents.length > 0 ? (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Spawned Agents", en: "Spawned agents" })}
            </p>
            <div className="space-y-2">
              {spawnedAgents.map((agent) => (
                <div
                  className="space-y-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-900 dark:border-emerald-500/20 dark:bg-emerald-500/10 dark:text-emerald-100"
                  key={agent.thread_id}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-emerald-100 px-2 py-1 font-semibold text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-100">
                      {agent.role ?? t(locale, { ru: "sub-agent", en: "sub-agent" })}
                    </span>
                    {agent.status ? (
                      <span className="rounded-full bg-white/80 px-2 py-1 font-medium text-emerald-700 dark:bg-zinc-950/60 dark:text-emerald-200">
                        {agent.status}
                      </span>
                    ) : null}
                    <span className="font-mono text-[11px] text-emerald-700/90 dark:text-emerald-200/90">
                      {agent.thread_id}
                    </span>
                  </div>
                  <div className="space-y-2 border-l border-emerald-300/70 pl-3 dark:border-emerald-500/30">
                    <div className="relative">
                      <span className="absolute -left-[1.05rem] top-1.5 h-2 w-2 rounded-full bg-emerald-500" />
                      <p className="font-semibold text-emerald-900 dark:text-emerald-100">
                        {t(locale, { ru: "Spawned", en: "Spawned" })}
                      </p>
                      <p className="text-[11px] leading-5 text-emerald-800/90 dark:text-emerald-100/90">
                        {t(locale, {
                          ru: "Root agent создал specialist thread через collaboration tool.",
                          en: "Root agent created a specialist thread via the collaboration tool."
                        })}
                      </p>
                    </div>
                    {agent.status ? (
                      <div className="relative">
                        <span className="absolute -left-[1.05rem] top-1.5 h-2 w-2 rounded-full bg-emerald-400" />
                        <p className="font-semibold text-emerald-900 dark:text-emerald-100">
                          {t(locale, { ru: "State", en: "State" })}
                        </p>
                        <p className="text-[11px] leading-5 text-emerald-800/90 dark:text-emerald-100/90">
                          {agent.status}
                        </p>
                      </div>
                    ) : null}
                    {agent.result_preview ? (
                      <div className="relative">
                        <span className="absolute -left-[1.05rem] top-1.5 h-2 w-2 rounded-full bg-emerald-300" />
                        <p className="font-semibold text-emerald-900 dark:text-emerald-100">
                          {t(locale, { ru: "Summary", en: "Summary" })}
                        </p>
                        <p className="line-clamp-3 text-[11px] leading-5 text-emerald-800/90 dark:text-emerald-100/90">
                          {agent.result_preview}
                        </p>
                      </div>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {skillRefs.length > 0 ? (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Skills", en: "Skills" })}
            </p>
            <div className="flex flex-wrap gap-2">
              {skillRefs.map((skill) => (
                <span
                  className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-200"
                  key={skill}
                >
                  {skill}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        {agentConfigReads.length > 0 ? (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Agent Config Reads", en: "Agent config reads" })}
            </p>
            <div className="flex flex-wrap gap-2">
              {agentConfigReads.map((agent) => (
                <span
                  className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800 dark:bg-amber-500/15 dark:text-amber-200"
                  key={agent}
                >
                  {agent}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        {additionalThreadIds.length > 0 ? (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Additional Threads", en: "Additional threads" })}
            </p>
            <div className="flex flex-wrap gap-2">
              {additionalThreadIds.map((threadId) => (
                <span
                  className="rounded-full bg-fuchsia-100 px-3 py-1 text-xs font-semibold text-fuchsia-800 dark:bg-fuchsia-500/15 dark:text-fuchsia-200"
                  key={threadId}
                >
                  {threadId}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        {delegationMarkers.length > 0 ? (
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Sub-agent Signals", en: "Sub-agent signals" })}
            </p>
            <div className="space-y-2">
              {delegationMarkers.map((marker) => (
                <p
                  className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-slate-300"
                  key={marker}
                >
                  {marker}
                </p>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    );
  }

  return null;
}

function tryExtractNestedMessage(value: string | null): string | null {
  if (!value) {
    return null;
  }

  const normalized = value.trim();
  if (!normalized) {
    return null;
  }

  const visited = new Set<string>();
  let current: unknown = normalized;

  while (typeof current === "string") {
    const text = current.trim();
    if (!text || visited.has(text)) {
      break;
    }
    visited.add(text);

    if (text.startsWith("{")) {
      try {
        current = JSON.parse(text);
        continue;
      } catch {
        return text;
      }
    }

    return text;
  }

  if (current && typeof current === "object") {
    const payload = current as Record<string, unknown>;
    if (typeof payload.error === "object" && payload.error !== null) {
      const nested = payload.error as Record<string, unknown>;
      if (typeof nested.message === "string" && nested.message.trim()) {
        return nested.message.trim();
      }
    }
    if (typeof payload.message === "string" && payload.message.trim()) {
      return tryExtractNestedMessage(payload.message);
    }
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail.trim();
    }
  }

  return normalized;
}

export function RunDetailsPanel({ locale, runId }: RunDetailsPanelProps) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loadingUser, setLoadingUser] = useState(true);
  const [run, setRun] = useState<Run | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [terminalSession, setTerminalSession] = useState<CodexSessionRead | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [loadingRun, setLoadingRun] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [resumingRun, setResumingRun] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());

  const activeTab = parseRunPageTab(searchParams.get("tab"));

  useEffect(() => {
    let cancelled = false;

    async function resolveUser() {
      const currentToken = getAccessToken();
      if (!currentToken) {
        if (!cancelled) {
          setToken(null);
          setUser(null);
          setLoadingUser(false);
        }
        return;
      }

      if (!cancelled) {
        setToken(currentToken);
      }

      try {
        const currentUser = await fetchCurrentUser(currentToken);
        if (!cancelled) {
          setUser(currentUser);
        }
      } catch {
        clearAccessToken();
        if (!cancelled) {
          setToken(null);
          setUser(null);
        }
      } finally {
        if (!cancelled) {
          setLoadingUser(false);
        }
      }
    }

    void resolveUser();

    return () => {
      cancelled = true;
    };
  }, []);

  const loadRunData = useCallback(async () => {
    if (!token) {
      return;
    }

    const [runPayload, eventsPayload, sessionPayload] = await Promise.all([
      fetchRun(runId, token),
      fetchRunEvents(runId, token),
      fetchRunTerminalSession(runId, token)
    ]);
    const workspacePayload = runPayload.workspace_id
      ? await fetchWorkspace(runPayload.workspace_id, token).catch(() => null)
      : null;
    setRun(runPayload);
    setWorkspace(workspacePayload);
    setTerminalSession(sessionPayload);
    setEvents(eventsPayload.items);
  }, [runId, token]);

  useEffect(() => {
    if (!token) {
      setRun(null);
      setWorkspace(null);
      setTerminalSession(null);
      setEvents([]);
      setLoadingRun(false);
      return;
    }

    let cancelled = false;
    setLoadingRun(true);

    async function load() {
      try {
        await loadRunData();
        if (!cancelled) {
          setErrorMessage(null);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(
            error instanceof Error
              ? error.message
              : t(locale, { ru: "Не удалось загрузить run.", en: "Failed to load run." })
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingRun(false);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [loadRunData, locale, token]);

  useEffect(() => {
    if (!token || !run || terminalStatuses.has(run.status)) {
      return;
    }

    const timer = setInterval(() => {
      void loadRunData().catch(() => undefined);
    }, 2000);

    return () => {
      clearInterval(timer);
    };
  }, [loadRunData, run, token]);

  useEffect(() => {
    if (!run?.started_at || terminalStatuses.has(run.status)) {
      return;
    }

    const timer = setInterval(() => {
      setNowMs(Date.now());
    }, 1000);

    return () => {
      clearInterval(timer);
    };
  }, [run?.finished_at, run?.started_at, run?.status]);

  const canCancel = useMemo(() => {
    if (!run) {
      return false;
    }
    return run.status === "running" || run.status === "starting_codex" || run.status === "resuming";
  }, [run]);
  const canResume = useMemo(() => {
    if (!run || !terminalSession) {
      return false;
    }
    return run.status === "interrupted" && terminalSession.resumable;
  }, [run, terminalSession]);
  const displaySummary = useMemo(() => {
    const normalized = tryExtractNestedMessage(run?.summary ?? null);
    if (!normalized) {
      return null;
    }
    if (normalized.startsWith("{\"type\":") || normalized.startsWith("{\"type\":")) {
      return null;
    }
    return normalized;
  }, [run?.summary]);
  const displayError = useMemo(
    () => tryExtractNestedMessage(run?.error_message ?? null),
    [run?.error_message]
  );
  const filteredChangedFiles = useMemo(() => {
    if (!workspace || !run) {
      return [];
    }
    if (terminalStatuses.has(run.status)) {
      return workspace.changed_files;
    }
    return workspace.changed_files.filter((path) => !isTemporaryExecutionPath(path));
  }, [run, workspace]);
  const hiddenTemporaryFilesCount = useMemo(() => {
    if (!workspace || !run || terminalStatuses.has(run.status)) {
      return 0;
    }
    return workspace.changed_files.filter((path) => isTemporaryExecutionPath(path)).length;
  }, [run, workspace]);

  async function onCancel() {
    if (!token || !run) {
      router.push("/auth/login");
      return;
    }

    setCancelling(true);
    setErrorMessage(null);
    try {
      const nextRun = await cancelRun(run.id, token);
      setRun(nextRun);
      const refreshedEvents = await fetchRunEvents(run.id, token);
      setEvents(refreshedEvents.items);
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : t(locale, { ru: "Не удалось отменить run.", en: "Failed to cancel run." })
      );
    } finally {
      setCancelling(false);
    }
  }

  async function onRefresh() {
    try {
      setErrorMessage(null);
      await loadRunData();
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : t(locale, { ru: "Не удалось обновить run.", en: "Failed to refresh run." })
      );
    }
  }

  async function onResume() {
    if (!token || !run) {
      router.push("/auth/login");
      return;
    }

    setResumingRun(true);
    setErrorMessage(null);
    try {
      const nextRun = await resumeRun(run.id, token);
      setRun(nextRun);
      await loadRunData();
    } catch (error) {
      setErrorMessage(
        error instanceof Error
          ? error.message
          : t(locale, { ru: "Не удалось возобновить run.", en: "Failed to resume run." })
      );
    } finally {
      setResumingRun(false);
    }
  }

  function onTabChange(tabId: RunPageTabId) {
    const nextParams = new URLSearchParams(searchParams.toString());

    if (tabId === "overview") {
      nextParams.delete("tab");
    } else {
      nextParams.set("tab", tabId);
    }

    const nextQuery = nextParams.toString();
    router.push(nextQuery ? `${pathname}?${nextQuery}` : pathname, { scroll: false });
  }

  if (loadingUser || loadingRun) {
    return (
      <div className="rounded-3xl border border-slate-200 bg-white px-5 py-4 text-sm text-slate-600 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:text-slate-300 dark:shadow-black/20">
        {loadingUser ? formatAuthLoading(locale) : t(locale, { ru: "Загружаем run...", en: "Loading run..." })}
      </div>
    );
  }

  if (!user) {
    return (
      <div className="rounded-3xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200">
        {t(locale, {
          ru: "Для просмотра run нужно авторизоваться в платформе.",
          en: "You need to sign in to view run details."
        })}
      </div>
    );
  }

  if (errorMessage || !run) {
    return (
      <div className="rounded-3xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-200">
        {errorMessage ?? t(locale, { ru: "Run не найден.", en: "Run not found." })}
      </div>
    );
  }

  const mainTabs = [
    {
      id: "overview" as const,
      label: t(locale, { ru: "Overview", en: "Overview" }),
      note: t(locale, { ru: "контекст и scm", en: "context and scm" })
    },
    {
      id: "activity" as const,
      label: t(locale, { ru: "Activity", en: "Activity" }),
      note: t(locale, { ru: "timeline и события", en: "timeline and events" })
    },
    {
      id: "report" as const,
      label: t(locale, { ru: "Report", en: "Report" }),
      note: t(locale, { ru: "фазы выполнения", en: "execution phases" })
    },
    {
      id: "terminal" as const,
      label: t(locale, { ru: "Terminal", en: "Terminal" }),
      note: t(locale, { ru: "live codex output", en: "live Codex output" })
    }
  ];
  const durationLabel = formatRunDuration(locale, run.started_at, run.finished_at, nowMs);
  const latestEvent = events[0] ?? null;
  const inputTokensLabel = formatCompactNumber(locale, terminalSession?.input_tokens ?? null);
  const outputTokensLabel = formatCompactNumber(locale, terminalSession?.output_tokens ?? null);
  const inputTokensCompactLabel = formatAbbreviatedNumber(locale, terminalSession?.input_tokens ?? null);
  const outputTokensCompactLabel = formatAbbreviatedNumber(locale, terminalSession?.output_tokens ?? null);

  const renderOverview = () => (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-6">
        <div className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex items-center gap-2">
            <FolderGit2 className="h-4 w-4 text-slate-500 dark:text-slate-400" />
            <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Контекст запуска", en: "Run context" })}
            </h2>
          </div>
          <div className="mt-4 grid gap-4 text-sm text-slate-600 dark:text-slate-300 md:grid-cols-2">
            <p>
              <span className="font-semibold text-slate-900 dark:text-slate-100">ID:</span> {run.id}
            </p>
            <p>
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Runtime:", en: "Runtime:" })}
              </span>{" "}
              {run.runtime_target}
            </p>
            <p>
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Базовая ветка:", en: "Base branch:" })}
              </span>{" "}
              {run.base_branch}
            </p>
            <p>
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Рабочая ветка:", en: "Working branch:" })}
              </span>{" "}
              {run.working_branch ?? "-"}
            </p>
            <p>
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Workspace ID:", en: "Workspace ID:" })}
              </span>{" "}
              {run.workspace_id ?? "-"}
            </p>
            <p>
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Время выполнения:", en: "Duration:" })}
              </span>{" "}
              {durationLabel}
            </p>
            {run.issue_number ? (
              <div className="md:col-span-2">
                <span className="font-semibold text-slate-900 dark:text-slate-100">
                  {t(locale, { ru: "Issue:", en: "Issue:" })}
                </span>{" "}
                <Link
                  className="font-semibold text-brand-700 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200"
                  href={`/repos/${encodeURIComponent(run.repo_owner)}/${encodeURIComponent(run.repo_name)}/issues/${run.issue_number}`}
                >
                  #{run.issue_number} {run.issue_title ?? ""}
                </Link>
              </div>
            ) : null}
            {run.task_text ? (
              <div className="md:col-span-2">
                <span className="font-semibold text-slate-900 dark:text-slate-100">
                  {t(locale, { ru: "Task brief:", en: "Task brief:" })}
                </span>
                <p className="mt-2 whitespace-pre-wrap leading-7 text-slate-700 dark:text-slate-200">
                  {run.task_text}
                </p>
              </div>
            ) : null}
            <div className="md:col-span-2">
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Путь workspace:", en: "Workspace path:" })}
              </span>{" "}
              <code className="break-all text-xs">{run.workspace_path ?? "-"}</code>
            </div>
            <div className="md:col-span-2">
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                {t(locale, { ru: "Путь репозитория:", en: "Repository path:" })}
              </span>{" "}
              <code className="break-all text-xs">{run.repo_path ?? "-"}</code>
            </div>
          </div>
        </div>

        {workspace ? (
          <div className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
            <div className="flex items-center gap-2">
              <GitBranch className="h-4 w-4 text-slate-500 dark:text-slate-400" />
              <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "SCM результат", en: "SCM result" })}
              </h2>
            </div>
            <div className="mt-4 grid gap-4 text-sm text-slate-600 dark:text-slate-300 md:grid-cols-2">
              <p>
                <span className="font-semibold text-slate-900 dark:text-slate-100">
                  {t(locale, { ru: "Статус workspace:", en: "Workspace status:" })}
                </span>{" "}
                {formatWorkspaceStatus(locale, workspace.status)}
              </p>
              <p>
                <span className="font-semibold text-slate-900 dark:text-slate-100">
                  {t(locale, { ru: "Текущая ветка:", en: "Current branch:" })}
                </span>{" "}
                {workspace.current_branch ?? "-"}
              </p>
              <p>
                <span className="font-semibold text-slate-900 dark:text-slate-100">
                  {t(locale, { ru: "Последний commit:", en: "Last commit:" })}
                </span>{" "}
                <code className="text-xs">{formatShortSha(workspace.last_commit_sha)}</code>
              </p>
              <p>
                <span className="font-semibold text-slate-900 dark:text-slate-100">
                  {t(locale, { ru: "Pull request:", en: "Pull request:" })}
                </span>{" "}
                {workspace.pull_request_number ? `#${workspace.pull_request_number}` : "-"}
              </p>
              <p>
                <span className="font-semibold text-slate-900 dark:text-slate-100">
                  {t(locale, { ru: "Commit time:", en: "Commit time:" })}
                </span>{" "}
                <LocalizedTimestamp locale={locale} value={workspace.committed_at} />
              </p>
              <p>
                <span className="font-semibold text-slate-900 dark:text-slate-100">
                  {t(locale, { ru: "Push time:", en: "Push time:" })}
                </span>{" "}
                <LocalizedTimestamp locale={locale} value={workspace.pushed_at} />
              </p>
              {workspace.last_commit_message ? (
                <div className="md:col-span-2">
                  <span className="font-semibold text-slate-900 dark:text-slate-100">
                    {t(locale, { ru: "Commit message:", en: "Commit message:" })}
                  </span>{" "}
                  <span>{workspace.last_commit_message}</span>
                </div>
              ) : null}
              {workspace.pull_request_url ? (
                <div className="md:col-span-2">
                  <a
                    className="inline-flex items-center gap-2 font-semibold text-brand-700 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200"
                    href={workspace.pull_request_url}
                    rel="noreferrer"
                    target="_blank"
                  >
                    <ExternalLink className="h-4 w-4" />
                    {t(locale, { ru: "Открыть draft PR", en: "Open draft PR" })}
                  </a>
                </div>
              ) : null}
              <div className="md:col-span-2">
                <span className="font-semibold text-slate-900 dark:text-slate-100">
                  {t(locale, {
                    ru: terminalStatuses.has(run.status)
                      ? "Tracked changes after run:"
                      : "Текущие tracked changes:",
                    en: terminalStatuses.has(run.status)
                      ? "Tracked changes after run:"
                      : "Current tracked changes:"
                  })}
                </span>{" "}
                {filteredChangedFiles.length > 0 ? (
                  <span>{filteredChangedFiles.join(", ")}</span>
                ) : (
                  <span>
                    {workspace.has_changes && !terminalStatuses.has(run.status)
                      ? t(locale, {
                          ru: "пока виден только временный execution scaffolding",
                          en: "only temporary execution scaffolding is visible right now"
                        })
                      : t(locale, { ru: "рабочее дерево чистое", en: "worktree is clean" })}
                  </span>
                )}
              </div>
              {hiddenTemporaryFilesCount > 0 ? (
                <div className="md:col-span-2 text-xs text-slate-500 dark:text-slate-400">
                  {t(locale, {
                    ru: `Временные execution-файлы скрыты из этого блока до завершения run: ${hiddenTemporaryFilesCount}.`,
                    en: `Temporary execution files are hidden from this block until the run finishes: ${hiddenTemporaryFilesCount}.`
                  })}
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>

      <aside className="space-y-4 xl:sticky xl:top-24 xl:self-start">
        <div className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 dark:border-zinc-800 dark:bg-zinc-900/70">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-slate-500 dark:text-slate-400" />
            <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Run profile", en: "Run profile" })}
            </h3>
          </div>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex items-start justify-between gap-4">
              <dt className="text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "Команда", en: "Team" })}
              </dt>
              <dd className="text-right font-semibold text-slate-900 dark:text-slate-100">
                <Link className="hover:text-brand-700 dark:hover:text-white" href={`/teams/${encodeURIComponent(run.team_slug)}`}>
                  {run.team_title}
                </Link>
              </dd>
            </div>
            <div className="flex items-start justify-between gap-4">
              <dt className="text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "Репозиторий", en: "Repository" })}
              </dt>
              <dd className="text-right font-semibold text-slate-900 dark:text-slate-100">
                <Link
                  className="hover:text-brand-700 dark:hover:text-white"
                  href={`/repos/${encodeURIComponent(run.repo_owner)}/${encodeURIComponent(run.repo_name)}`}
                >
                  {run.repo_full_name}
                </Link>
              </dd>
            </div>
            <div className="flex items-start justify-between gap-4">
              <dt className="text-slate-500 dark:text-slate-400">{t(locale, { ru: "Статус", en: "Status" })}</dt>
              <dd className="text-right font-semibold text-slate-900 dark:text-slate-100">
                <RunStatusBadge locale={locale} status={run.status} />
              </dd>
            </div>
            <div className="flex items-start justify-between gap-4">
              <dt className="text-slate-500 dark:text-slate-400">{t(locale, { ru: "Runtime", en: "Runtime" })}</dt>
              <dd className="text-right font-semibold text-slate-900 dark:text-slate-100">{run.runtime_target}</dd>
            </div>
          </dl>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex items-center gap-2">
            <Clock3 className="h-4 w-4 text-slate-500 dark:text-slate-400" />
            <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Timeline", en: "Timeline" })}
            </h3>
          </div>
          <ul className="mt-4 space-y-3 text-sm text-slate-700 dark:text-slate-200">
            <li className="flex items-center justify-between gap-3">
              <span>{t(locale, { ru: "Создан", en: "Created" })}</span>
              <span className="text-right"><LocalizedTimestamp locale={locale} value={run.created_at} /></span>
            </li>
            <li className="flex items-center justify-between gap-3">
              <span>{t(locale, { ru: "Старт", en: "Started" })}</span>
              <span className="text-right"><LocalizedTimestamp locale={locale} value={run.started_at} /></span>
            </li>
            <li className="flex items-center justify-between gap-3">
              <span>{t(locale, { ru: "Финиш", en: "Finished" })}</span>
              <span className="text-right"><LocalizedTimestamp locale={locale} value={run.finished_at} /></span>
            </li>
            <li className="flex items-center justify-between gap-3">
              <span>{t(locale, { ru: "Длительность", en: "Duration" })}</span>
              <span className="font-semibold">{durationLabel}</span>
            </li>
          </ul>
        </div>

        <div className="rounded-3xl border border-slate-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-slate-500 dark:text-slate-400" />
            <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Сводка активности", en: "Activity summary" })}
            </h3>
          </div>
          <ul className="mt-4 space-y-3 text-sm text-slate-700 dark:text-slate-200">
            <li className="flex items-center justify-between gap-3">
              <span>{t(locale, { ru: "Событий", en: "Events" })}</span>
              <span className="font-semibold">{events.length}</span>
            </li>
            <li className="flex items-center justify-between gap-3">
              <span>{t(locale, { ru: "Workspace", en: "Workspace" })}</span>
              <span className="font-semibold">{workspace?.status ?? "-"}</span>
            </li>
            <li className="flex items-center justify-between gap-3">
              <span>{t(locale, { ru: "Pull request", en: "Pull request" })}</span>
              <span className="font-semibold">{workspace?.pull_request_number ? `#${workspace.pull_request_number}` : "-"}</span>
            </li>
          </ul>
        </div>
      </aside>
    </div>
  );

  const renderActivity = () => (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="rounded-3xl border border-slate-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-center gap-2">
          <ScrollText className="h-4 w-4 text-slate-500 dark:text-slate-400" />
          <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
            {t(locale, { ru: "События run", en: "Run events" })}
          </h2>
        </div>
        {events.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">
            {t(locale, { ru: "События пока не записаны.", en: "No run events have been recorded yet." })}
          </p>
        ) : (
          <ol className="mt-4 space-y-3">
            {events.map((event) => (
              <li
                className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 dark:border-zinc-800 dark:bg-zinc-900/70"
                key={event.id}
              >
                <div className="mb-2 flex items-center justify-between gap-3">
                  <span className="rounded-full bg-slate-200 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-700 dark:bg-zinc-800 dark:text-slate-300">
                    {event.event_type}
                  </span>
                  <span className="text-xs text-slate-500 dark:text-slate-400">
                    <LocalizedTimestamp locale={locale} value={event.created_at} />
                  </span>
                </div>
                <p className="text-sm text-slate-700 dark:text-slate-200">
                  {extractEventMessage(event, locale)}
                </p>
                {renderEventAuditDetails(event, locale)}
              </li>
            ))}
          </ol>
        )}
      </div>

      <aside className="space-y-4 xl:sticky xl:top-24 xl:self-start">
        <div className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 dark:border-zinc-800 dark:bg-zinc-900/70">
          <div className="flex items-center gap-2">
            <Clock3 className="h-4 w-4 text-slate-500 dark:text-slate-400" />
            <h3 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
              {t(locale, { ru: "Последняя активность", en: "Latest activity" })}
            </h3>
          </div>
          <div className="mt-4 text-sm text-slate-700 dark:text-slate-200">
            {latestEvent ? (
              <div className="space-y-2">
                <p className="font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
                  {latestEvent.event_type}
                </p>
                <p>{extractEventMessage(latestEvent, locale)}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  <LocalizedTimestamp locale={locale} value={latestEvent.created_at} />
                </p>
              </div>
            ) : (
              <p className="text-slate-500 dark:text-slate-400">
                {t(locale, { ru: "Событий ещё нет.", en: "No activity yet." })}
              </p>
            )}
          </div>
        </div>
      </aside>
    </div>
  );

  return (
    <section className="space-y-6">
      <div className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
        <div className="border-b border-slate-200 bg-[linear-gradient(135deg,rgba(15,23,42,0.02),rgba(59,130,246,0.08),rgba(16,185,129,0.08))] px-6 py-8 dark:border-zinc-800 dark:bg-[linear-gradient(135deg,rgba(255,255,255,0.03),rgba(37,99,235,0.12),rgba(16,185,129,0.12))]">
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_460px] xl:items-start">
            <div className="space-y-5">
              <div className="flex flex-wrap gap-2">
                <RunStatusBadge locale={locale} status={run.status} />
                <span className="inline-flex items-center gap-1.5 rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-950/90 dark:text-slate-200 dark:ring-zinc-700">
                  <PlaySquare className="h-3.5 w-3.5" />
                  {run.team_title}
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-950/90 dark:text-slate-200 dark:ring-zinc-700">
                  <FolderGit2 className="h-3.5 w-3.5" />
                  {run.repo_full_name}
                </span>
                {run.issue_number ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 dark:bg-zinc-950/90 dark:text-slate-200 dark:ring-zinc-700">
                    #{run.issue_number}
                  </span>
                ) : null}
              </div>

              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-[0.32em] text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Run session", en: "Run session" })}
                </p>
                <h1 className="text-3xl font-black tracking-tight text-slate-950 dark:text-slate-50">
                  {run.title}
                </h1>
                <p className="max-w-3xl text-sm leading-7 text-slate-600 dark:text-slate-300">
                  {displaySummary ??
                    t(locale, {
                      ru: "Summary для run не был задан явно; детали смотри в TASK.md и terminal output.",
                      en: "The run summary was not provided explicitly; see TASK.md and the terminal output for details."
                    })}
                </p>
              </div>

              <dl className="grid gap-4 text-sm sm:grid-cols-3">
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
                    {t(locale, { ru: "Команда", en: "Team" })}
                  </dt>
                  <dd className="mt-1 font-semibold text-slate-900 dark:text-slate-100">{run.team_title}</dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
                    {t(locale, { ru: "Runtime", en: "Runtime" })}
                  </dt>
                  <dd className="mt-1 font-semibold text-slate-900 dark:text-slate-100">{run.runtime_target}</dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
                    {t(locale, { ru: "Working branch", en: "Working branch" })}
                  </dt>
                  <dd className="mt-1 font-semibold text-slate-900 dark:text-slate-100">{run.working_branch ?? "-"}</dd>
                </div>
              </dl>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-2 xl:self-start">
              <div className="rounded-3xl border border-slate-200 bg-white/90 p-4 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/90">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Duration", en: "Duration" })}
                </p>
                <p className="mt-3 text-3xl font-black text-slate-950 dark:text-slate-50">{durationLabel}</p>
                <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
                  <LocalizedTimestamp locale={locale} value={run.started_at} />
                </p>
              </div>

              <div className="rounded-3xl border border-slate-200 bg-white/90 p-4 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/90">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Workspace", en: "Workspace" })}
                </p>
                <p className="mt-3 break-words text-xl font-black leading-tight text-slate-950 dark:text-slate-50">
                  {workspace ? formatWorkspaceStatus(locale, workspace.status) : run.status.replaceAll("_", " ")}
                </p>
                <p className="mt-2 break-all text-sm text-slate-600 dark:text-slate-300">
                  {run.workspace_id ?? t(locale, { ru: "ещё не создан", en: "not created yet" })}
                </p>
              </div>

              <div className="rounded-3xl border border-slate-200 bg-white/90 p-4 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/90">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Automation", en: "Automation" })}
                </p>
                <p className="mt-3 text-2xl font-black text-slate-950 dark:text-slate-50">
                  {run.status === "resuming"
                    ? t(locale, { ru: "возобновление", en: "resuming" })
                    : run.status === "interrupted"
                      ? t(locale, { ru: "прерван", en: "interrupted" })
                      : run.pr_url
                        ? t(locale, { ru: "draft PR готов", en: "draft PR ready" })
                        : run.status === "completed"
                          ? t(locale, { ru: "завершен", en: "completed" })
                          : run.status === "failed" || run.status === "cancelled"
                            ? t(locale, { ru: "остановлен", en: "halted" })
                            : t(locale, { ru: "в работе", en: "in progress" })}
                </p>
                <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
                  {t(locale, {
                    ru: `${events.length} событий за run`,
                    en: `${events.length} events recorded`
                  })}
                </p>
              </div>

              <div className="rounded-3xl border border-slate-200 bg-white/90 p-4 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/90">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                  {t(locale, { ru: "Token usage", en: "Token usage" })}
                </p>
                <div className="mt-3 grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
                      {t(locale, { ru: "Input", en: "Input" })}
                    </p>
                    <p className="mt-1 text-xl font-black text-slate-950 dark:text-slate-50">
                      {inputTokensCompactLabel}
                    </p>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{inputTokensLabel}</p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
                      {t(locale, { ru: "Output", en: "Output" })}
                    </p>
                    <p className="mt-1 text-xl font-black text-slate-950 dark:text-slate-50">
                      {outputTokensCompactLabel}
                    </p>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{outputTokensLabel}</p>
                  </div>
                </div>
                <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
                  {terminalSession
                    ? t(locale, {
                        ru: "Берется из последнего turn.completed в terminal stream.",
                        en: "Derived from the latest turn.completed event in the terminal stream."
                      })
                    : t(locale, {
                        ru: "Появится после старта Codex-сессии.",
                        en: "Appears after the Codex session starts."
                      })}
                </p>
              </div>

              <div className="flex flex-wrap gap-2 sm:col-span-2">
                <Button onClick={() => void onRefresh()} type="button" variant="secondary">
                  <RefreshCcw className="mr-2 h-4 w-4" />
                  {t(locale, { ru: "Обновить", en: "Refresh" })}
                </Button>
                {canResume ? (
                  <Button disabled={resumingRun} onClick={() => void onResume()} type="button" variant="secondary">
                    {resumingRun ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <RotateCcw className="mr-2 h-4 w-4" />
                    )}
                    {t(locale, { ru: "Возобновить Codex", en: "Resume Codex session" })}
                  </Button>
                ) : null}
                {canCancel ? (
                  <Button disabled={cancelling} onClick={() => void onCancel()} type="button" variant="ghost">
                    {cancelling ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Square className="mr-2 h-4 w-4" />
                    )}
                    {t(locale, { ru: "Остановить run", en: "Stop run" })}
                  </Button>
                ) : null}
              </div>
            </div>
          </div>
        </div>

        <div className="border-b border-slate-200 bg-white px-4 py-4 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="flex flex-wrap gap-3">
            {mainTabs.map((tab) => {
              const active = tab.id === activeTab;
              return (
                <button
                  className={cn(
                    "rounded-2xl border px-4 py-3 text-left transition",
                    active
                      ? "border-slate-300 bg-slate-100 text-slate-950 dark:border-zinc-700 dark:bg-white dark:text-zinc-950"
                      : "border-slate-200 bg-white text-slate-700 hover:border-slate-300 dark:border-zinc-800 dark:bg-zinc-950 dark:text-slate-200 dark:hover:border-zinc-700"
                  )}
                  key={tab.id}
                  onClick={() => onTabChange(tab.id)}
                  type="button"
                >
                  <div className="text-sm font-semibold">{tab.label}</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">{tab.note}</div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="px-6 py-6">
          {displayError ? (
            <div className="mb-6 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-200">
              {displayError}
            </div>
          ) : null}

          {activeTab === "overview" ? renderOverview() : null}
          {activeTab === "activity" ? renderActivity() : null}
          {activeTab === "report" ? <RunReportPanel locale={locale} report={run.run_report} /> : null}
          {activeTab === "terminal" ? (
            <div className="space-y-4">
              <div className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5 dark:border-zinc-800 dark:bg-zinc-900/70">
                <div className="flex items-center gap-2">
                  <SquareTerminal className="h-4 w-4 text-slate-500 dark:text-slate-400" />
                  <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
                    {t(locale, { ru: "Live terminal", en: "Live terminal" })}
                  </h2>
                </div>
                <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
                  {t(locale, {
                    ru: "PTY-поток Codex CLI для текущего run. Здесь виден живой output и финальный exit state.",
                    en: "PTY stream from the Codex CLI for this run. This is the live output and final exit state."
                  })}
                </p>
              </div>
              <RunTerminalPanel locale={locale} runId={run.id} runStatus={run.status} token={token!} />
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
