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

function looksLikeCodeSummary(value: string): boolean {
  const lowered = value.toLowerCase();
  return [
    "classname=",
    "<div",
    "</div",
    "function ",
    "const ",
    "return ",
    "=>",
    "import ",
    "export "
  ].some((marker) => lowered.includes(marker));
}

export function normalizeRunSummaryText(value: string | null): string | null {
  const extracted = tryExtractNestedMessage(value);
  if (!extracted) {
    return null;
  }

  let normalized = extracted
    .replace(/\u001b\[[0-9;]*m/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/`([^`]+)`/g, "$1");

  const paragraph = normalized.match(/\n\s*\n/);
  if (paragraph) {
    normalized = normalized.slice(0, paragraph.index);
  }

  for (const marker of ["Main files changed:", "Validation:", "Most logical next step:", "Notes:", "## Notes"]) {
    const markerIndex = normalized.indexOf(marker);
    if (markerIndex > 0) {
      normalized = normalized.slice(0, markerIndex);
      break;
    }
  }

  normalized = normalized.replace(/\s+/g, " ").trim();
  if (!normalized || looksLikeCodeSummary(normalized)) {
    return null;
  }

  if (normalized.length <= 320) {
    return normalized;
  }

  const sentenceBoundary = Math.max(
    normalized.lastIndexOf(". ", 320),
    normalized.lastIndexOf("! ", 320),
    normalized.lastIndexOf("? ", 320)
  );
  if (sentenceBoundary >= 120) {
    return normalized.slice(0, sentenceBoundary + 1).trim();
  }

  return `${normalized.slice(0, 317).trimEnd()}...`;
}
