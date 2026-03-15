"use client";

import { useEffect, useRef, useState } from "react";
import { TerminalSquare } from "lucide-react";
import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";

import { LocalizedTimestamp } from "@/components/ui/localized-timestamp";
import {
  buildRunTerminalWebSocketUrl,
  fetchRunTerminalSession,
  type RuntimeTarget,
  type RunStatus,
  type TerminalSessionRead
} from "@/lib/api";
import { t, type Locale } from "@/lib/i18n";

const terminalStatuses = new Set<RunStatus | string>(["completed", "interrupted", "failed", "cancelled"]);

type RunTerminalPanelProps = {
  locale: Locale;
  runId: string;
  runStatus: RunStatus;
  runtimeTarget: RuntimeTarget;
  token: string;
};

type TerminalStreamPayload =
  | { type: "output"; offset: number; text: string }
  | {
      type: "status";
      status: TerminalSessionRead["status"];
      exit_code: number | null;
      summary_text: string | null;
      error_message: string | null;
    };

type CodexEventLine = {
  type?: string;
  message?: unknown;
  detail?: unknown;
  item?: {
    type?: string;
    text?: unknown;
    command?: unknown;
    aggregated_output?: unknown;
    exit_code?: unknown;
    status?: unknown;
  };
  error?: unknown;
  usage?: {
    input_tokens?: unknown;
    output_tokens?: unknown;
  };
};

type ClaudeEventLine = {
  type?: string;
  subtype?: unknown;
  result?: unknown;
  errors?: unknown;
  message?: {
    content?: Array<{
      type?: string;
      text?: unknown;
    }>;
  };
};

type ClaudeTextContentPart = {
  type: "text";
  text: string;
};

function normalizeTerminalText(value: string): string {
  return value.replace(/\r?\n/g, "\r\n");
}

function isIgnorableCodexWarning(line: string): boolean {
  return (
    line.includes("WARN codex_core::shell_snapshot: Failed to delete shell snapshot") ||
    line.includes("WARN codex_core::file_watcher: failed to unwatch")
  );
}

function stringifyUnknown(value: unknown): string | null {
  if (typeof value === "string") {
    const normalized = value.trim();
    return normalized.length > 0 ? normalized : null;
  }
  return null;
}

function extractNestedMessage(value: unknown): string | null {
  if (typeof value === "string") {
    const normalized = value.trim();
    if (!normalized) {
      return null;
    }
    if (!normalized.startsWith("{")) {
      return normalized;
    }
    try {
      return extractNestedMessage(JSON.parse(normalized));
    } catch {
      return normalized;
    }
  }

  if (!value || typeof value !== "object") {
    return null;
  }

  const payload = value as Record<string, unknown>;
  return (
    extractNestedMessage(payload.error) ??
    stringifyUnknown(payload.message) ??
    stringifyUnknown(payload.detail) ??
    null
  );
}

function isClaudeTextContentPart(value: unknown): value is ClaudeTextContentPart {
  if (!value || typeof value !== "object") {
    return false;
  }

  const item = value as { type?: unknown; text?: unknown };
  return item.type === "text" && typeof item.text === "string";
}

function renderCodexJsonLine(line: string, locale: Locale): string | null {
  if (isIgnorableCodexWarning(line)) {
    return null;
  }

  if (!line.trim().startsWith("{")) {
    return normalizeTerminalText(`${line}\n`);
  }

  let payload: CodexEventLine;
  try {
    payload = JSON.parse(line) as CodexEventLine;
  } catch {
    return normalizeTerminalText(`${line}\n`);
  }

  switch (payload.type) {
    case "thread.started":
      return null;
    case "turn.started":
      return normalizeTerminalText(
        `${t(locale, { ru: "Запуск turn...", en: "Starting turn..." })}\n`
      );
    case "turn.completed": {
      const inputTokens = typeof payload.usage?.input_tokens === "number" ? payload.usage.input_tokens : null;
      const outputTokens = typeof payload.usage?.output_tokens === "number" ? payload.usage.output_tokens : null;
      const suffix =
        inputTokens !== null || outputTokens !== null
          ? ` (${t(locale, { ru: "tokens", en: "tokens" })}: ${inputTokens ?? "-"} in / ${outputTokens ?? "-"} out)`
          : "";
      return normalizeTerminalText(
        `${t(locale, { ru: "Turn завершен", en: "Turn completed" })}${suffix}\n`
      );
    }
    case "turn.failed": {
      const message =
        extractNestedMessage(payload.error) ??
        extractNestedMessage(payload.message) ??
        t(locale, { ru: "Codex завершился с ошибкой.", en: "Codex failed." });
      return normalizeTerminalText(`${message}\n`);
    }
    case "item.started": {
      if (payload.item?.type === "command_execution") {
        const command = stringifyUnknown(payload.item.command);
        if (command) {
          return normalizeTerminalText(`$ ${command}\n`);
        }
      }
      return null;
    }
    case "item.completed": {
      if (payload.item?.type === "agent_message") {
        const text = stringifyUnknown(payload.item.text);
        return text ? normalizeTerminalText(`${text}\n\n`) : null;
      }
      if (payload.item?.type === "command_execution") {
        const output = stringifyUnknown(payload.item.aggregated_output);
        const exitCode =
          typeof payload.item.exit_code === "number" ? payload.item.exit_code : null;
        const statusText = stringifyUnknown(payload.item.status);
        const parts: string[] = [];
        if (output) {
          parts.push(output);
        }
        if (exitCode !== null && exitCode !== 0) {
          parts.push(
            t(locale, {
              ru: `Команда завершилась с exit code ${exitCode}.`,
              en: `Command exited with code ${exitCode}.`
            })
          );
        } else if (statusText === "failed") {
          parts.push(
            t(locale, {
              ru: "Команда завершилась с ошибкой.",
              en: "Command failed."
            })
          );
        }
        return parts.length > 0 ? normalizeTerminalText(`${parts.join("\n")}\n`) : null;
      }
      return null;
    }
    default: {
      const nestedMessage =
        extractNestedMessage(payload.error) ??
        extractNestedMessage(payload.message) ??
        extractNestedMessage(payload.detail);
      return nestedMessage ? normalizeTerminalText(`${nestedMessage}\n`) : null;
    }
  }
}

function extractClaudeAssistantText(message: ClaudeEventLine["message"]): string | null {
  if (!message || !Array.isArray(message.content)) {
    return null;
  }

  const parts = message.content
    .filter(isClaudeTextContentPart)
    .map((item) => item.text.trim())
    .filter((item) => item.length > 0);

  return parts.length > 0 ? parts.join("\n\n") : null;
}

function extractClaudeErrors(value: unknown): string | null {
  if (!Array.isArray(value)) {
    return null;
  }

  for (const item of value) {
    const message = extractNestedMessage(item);
    if (message) {
      return message;
    }
  }

  return null;
}

function renderClaudeJsonLine(line: string, locale: Locale): string | null {
  if (!line.trim().startsWith("{")) {
    return normalizeTerminalText(`${line}\n`);
  }

  let payload: ClaudeEventLine;
  try {
    payload = JSON.parse(line) as ClaudeEventLine;
  } catch {
    return normalizeTerminalText(`${line}\n`);
  }

  switch (payload.type) {
    case "system":
    case "user":
      return null;
    case "assistant": {
      const text = extractClaudeAssistantText(payload.message);
      return text ? normalizeTerminalText(`${text}\n\n`) : null;
    }
    case "result": {
      const result = stringifyUnknown(payload.result);
      if (result) {
        return normalizeTerminalText(`${result}\n`);
      }
      const errorMessage = extractClaudeErrors(payload.errors);
      if (errorMessage) {
        return normalizeTerminalText(`${errorMessage}\n`);
      }
      if (typeof payload.subtype === "string" && payload.subtype.trim().length > 0) {
        return normalizeTerminalText(
          `${t(locale, {
            ru: `Claude завершил поток: ${payload.subtype}.`,
            en: `Claude ended the stream with subtype: ${payload.subtype}.`
          })}\n`
        );
      }
      return null;
    }
    default: {
      const nestedMessage =
        extractNestedMessage(payload.message) ??
        extractNestedMessage(payload.errors) ??
        stringifyUnknown(payload.result);
      return nestedMessage ? normalizeTerminalText(`${nestedMessage}\n`) : null;
    }
  }
}

function renderTerminalChunk(
  rawText: string,
  locale: Locale,
  buffer: string,
  runtimeTarget: RuntimeTarget
): { output: string; buffer: string } {
  const combined = `${buffer}${rawText}`;
  const normalized = combined.replace(/\r\n/g, "\n");
  const lines = normalized.split("\n");
  const nextBuffer = lines.pop() ?? "";
  const output = lines
    .map((line) =>
      runtimeTarget === "claude_code"
        ? renderClaudeJsonLine(line, locale)
        : renderCodexJsonLine(line, locale)
    )
    .filter((line): line is string => Boolean(line))
    .join("");
  return { output, buffer: nextBuffer };
}

export function RunTerminalPanel({
  locale,
  runId,
  runStatus,
  runtimeTarget,
  token
}: RunTerminalPanelProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const terminalRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const websocketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const lastOffsetRef = useRef(-1);
  const runStatusRef = useRef<RunStatus>(runStatus);
  const sessionRef = useRef<TerminalSessionRead | null>(null);
  const lineBufferRef = useRef("");

  const [session, setSession] = useState<TerminalSessionRead | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [connectionState, setConnectionState] = useState<"waiting" | "connecting" | "streaming" | "closed" | "error">("waiting");

  useEffect(() => {
    runStatusRef.current = runStatus;
  }, [runStatus]);

  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  useEffect(() => {
    lastOffsetRef.current = -1;
    setSession(null);
    setSessionError(null);
    setConnectionState("waiting");
    lineBufferRef.current = "";
    terminalRef.current?.clear();
  }, [runId]);

  useEffect(() => {
    const terminal = new Terminal({
      convertEol: false,
      cursorBlink: false,
      disableStdin: true,
      fontFamily: '"IBM Plex Mono", "SFMono-Regular", ui-monospace, monospace',
      fontSize: 13,
      lineHeight: 1.4,
      theme: {
        background: "#09090b",
        foreground: "#e5e7eb",
        cursor: "#e5e7eb",
        selectionBackground: "rgba(255,255,255,0.18)",
        black: "#09090b",
        brightBlack: "#3f3f46",
        red: "#fb7185",
        brightRed: "#fda4af",
        green: "#4ade80",
        brightGreen: "#86efac",
        yellow: "#facc15",
        brightYellow: "#fde047",
        blue: "#60a5fa",
        brightBlue: "#93c5fd",
        magenta: "#c084fc",
        brightMagenta: "#d8b4fe",
        cyan: "#22d3ee",
        brightCyan: "#67e8f9",
        white: "#e5e7eb",
        brightWhite: "#ffffff"
      }
    });
    const fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);

    terminalRef.current = terminal;
    fitAddonRef.current = fitAddon;

    if (containerRef.current) {
      terminal.open(containerRef.current);
      fitAddon.fit();
    }

    return () => {
      resizeObserverRef.current?.disconnect();
      resizeObserverRef.current = null;
      fitAddonRef.current?.dispose();
      fitAddonRef.current = null;
      terminalRef.current?.dispose();
      terminalRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!containerRef.current || !fitAddonRef.current) {
      return;
    }

    const fit = () => fitAddonRef.current?.fit();
    fit();
    resizeObserverRef.current?.disconnect();
    resizeObserverRef.current = new ResizeObserver(() => fit());
    resizeObserverRef.current.observe(containerRef.current);
    window.addEventListener("resize", fit);

    return () => {
      window.removeEventListener("resize", fit);
      resizeObserverRef.current?.disconnect();
      resizeObserverRef.current = null;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    function writeSystemLine(text: string) {
      const terminal = terminalRef.current;
      if (!terminal) {
        return;
      }
      terminal.writeln(`\r\n\x1b[90m${text}\x1b[0m`);
    }

    function scheduleReconnect(delayMs: number) {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      reconnectTimerRef.current = setTimeout(() => {
        void connect();
      }, delayMs);
    }

    function closeSocket() {
      if (websocketRef.current) {
        websocketRef.current.close();
        websocketRef.current = null;
      }
    }

    async function connect() {
      if (cancelled) {
        return;
      }

      setConnectionState("connecting");
      setSessionError(null);

      try {
        const currentSession = await fetchRunTerminalSession(runId, token);
        if (cancelled) {
          return;
        }

        if (!currentSession) {
          setSession(null);
          setConnectionState("waiting");
          if (!terminalStatuses.has(runStatusRef.current)) {
            scheduleReconnect(1500);
          }
          return;
        }

        setSession(currentSession);
        closeSocket();

        const socket = new WebSocket(buildRunTerminalWebSocketUrl(runId, token));
        websocketRef.current = socket;

        socket.addEventListener("open", () => {
          if (cancelled) {
            return;
          }
          setConnectionState("streaming");
        });

        socket.addEventListener("message", (event) => {
          if (cancelled) {
            return;
          }

          try {
            const payload = JSON.parse(event.data) as TerminalStreamPayload;

            if (payload.type === "output") {
              if (payload.offset <= lastOffsetRef.current) {
                return;
              }
              lastOffsetRef.current = payload.offset;
              const rendered = renderTerminalChunk(
                payload.text,
                locale,
                lineBufferRef.current,
                runtimeTarget
              );
              lineBufferRef.current = rendered.buffer;
              if (rendered.output) {
                terminalRef.current?.write(rendered.output);
              }
              return;
            }

            setSession((current) => {
              if (!current) {
                return current;
              }
              return {
                ...current,
                status: payload.status,
                exit_code: payload.exit_code,
                summary_text: payload.summary_text,
                error_message: payload.error_message,
                finished_at:
                  payload.status === "completed" ||
                  payload.status === "interrupted" ||
                  payload.status === "failed" ||
                  payload.status === "cancelled"
                    ? new Date().toISOString()
                    : current.finished_at
              };
            });
          } catch {
            writeSystemLine(
              t(locale, {
                ru: "Получен некорректный terminal payload.",
                en: "Received an invalid terminal payload."
              })
            );
          }
        });

        socket.addEventListener("close", () => {
          if (cancelled) {
            return;
          }
          if (lineBufferRef.current.trim()) {
            terminalRef.current?.write(normalizeTerminalText(`${lineBufferRef.current}\n`));
            lineBufferRef.current = "";
          }
          setConnectionState("closed");
          websocketRef.current = null;
          if (sessionRef.current && !terminalStatuses.has(sessionRef.current.status)) {
            scheduleReconnect(1000);
          }
        });

        socket.addEventListener("error", () => {
          if (cancelled) {
            return;
          }
          setConnectionState("error");
          setSessionError(
            t(locale, {
              ru: "WebSocket терминала оборвался. Повторное подключение будет выполнено автоматически.",
              en: "Terminal WebSocket dropped. The client will retry automatically."
            })
          );
        });
      } catch (error) {
        if (cancelled) {
          return;
        }
        setConnectionState("error");
        setSessionError(
          error instanceof Error
            ? error.message
            : t(locale, {
                ru: "Не удалось подключиться к терминалу run.",
                en: "Failed to attach to the run terminal."
              })
        );
        if (!terminalStatuses.has(runStatusRef.current)) {
          scheduleReconnect(2000);
        }
      }
    }

    void connect();

    return () => {
      cancelled = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      closeSocket();
    };
  }, [locale, runId, runtimeTarget, token]);

  return (
    <section className="space-y-4 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:shadow-black/20">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-black text-slate-900 dark:text-slate-50">
            <TerminalSquare className="h-5 w-5" />
            {t(locale, { ru: "Live terminal", en: "Live terminal" })}
          </h2>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
            {t(locale, {
              ru:
                runtimeTarget === "claude_code"
                  ? "Terminal привязан к host-side Claude Code session. Панель показывает нормализованный live-лог без интерактивного stdin из браузера."
                  : "Terminal привязан к host-side Codex PTY. Панель показывает нормализованный live-лог без интерактивного stdin из браузера.",
              en:
                runtimeTarget === "claude_code"
                  ? "The terminal is attached to the host-side Claude Code session. The panel renders a normalized live log without interactive stdin from the browser."
                  : "The terminal is attached to the host-side Codex PTY. The panel renders a normalized live log without interactive stdin from the browser."
            })}
          </p>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600 dark:bg-zinc-900/70 dark:text-slate-300">
          {connectionState}
        </span>
      </div>

      {sessionError ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-200">
          {sessionError}
        </div>
      ) : null}

      {session ? (
        <div className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-sm text-slate-600 dark:border-zinc-800 dark:bg-zinc-900/70 dark:text-slate-300 md:grid-cols-2 xl:grid-cols-4">
          <p>
            <span className="font-semibold text-slate-900 dark:text-slate-100">PID:</span> {session.pid ?? "-"}
          </p>
          <p>
            <span className="font-semibold text-slate-900 dark:text-slate-100">Exit code:</span> {session.exit_code ?? "-"}
          </p>
          <p>
            <span className="font-semibold text-slate-900 dark:text-slate-100">
              {t(locale, { ru: "Старт:", en: "Started:" })}
            </span>{" "}
            <LocalizedTimestamp locale={locale} value={session.started_at} />
          </p>
          <p>
            <span className="font-semibold text-slate-900 dark:text-slate-100">
              {t(locale, { ru: "Финиш:", en: "Finished:" })}
            </span>{" "}
            <LocalizedTimestamp locale={locale} value={session.finished_at} />
          </p>
          <div className="md:col-span-2 xl:col-span-4">
            <span className="font-semibold text-slate-900 dark:text-slate-100">Command:</span>{" "}
            <code className="break-all text-xs">{session.command.join(" ")}</code>
          </div>
          <div className="md:col-span-2 xl:col-span-4">
            <span className="font-semibold text-slate-900 dark:text-slate-100">
              {t(locale, { ru: "Рабочий каталог:", en: "Working directory:" })}
            </span>{" "}
            <code className="break-all text-xs">{session.repo_path}</code>
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3 text-sm text-slate-500 dark:border-zinc-800 dark:bg-zinc-900/70 dark:text-slate-400">
          {t(locale, {
            ru: "Terminal session пока не создана. Если run еще стартует, панель подключится автоматически после появления host-side session.",
            en: "The terminal session has not been created yet. If the run is still starting, the panel will connect automatically once the host-side session appears."
          })}
        </div>
      )}

      <div className="overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-950">
        <div className="border-b border-zinc-800 px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-zinc-400">
          {runtimeTarget === "claude_code" ? "claude -p" : "codex exec"}
        </div>
        <div className="h-[30rem] w-full" ref={containerRef} />
      </div>
    </section>
  );
}
