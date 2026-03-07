export type Agent = {
  id: string;
  slug: string;
  title: string;
  short_description: string;
  full_description: string | null;
  category: string | null;
  author_name: string;
  status: "draft" | "published" | "archived" | "hidden";
  verification_status: "none" | "validated" | "verified";
  created_at: string;
  updated_at: string;
};

export type Team = {
  id: string;
  slug: string;
  title: string;
  description: string | null;
  author_name: string;
  status: "draft" | "published" | "archived" | "hidden";
  created_at: string;
  updated_at: string;
};

export type TeamItem = {
  id: string;
  team_id: string;
  agent_id: string;
  agent_slug: string;
  role_name: string;
  order_index: number;
  config_json: Record<string, unknown> | null;
  is_required: boolean;
};

export type TeamDetails = Team & {
  items: TeamItem[];
};

export type Review = {
  id: string;
  user_id: string;
  user_display_name: string;
  entity_type: "agent" | "team";
  entity_id: string;
  rating: number;
  text: string | null;
  works_as_expected: boolean;
  outdated_flag: boolean;
  unsafe_flag: boolean;
  created_at: string;
  updated_at: string;
};

export type RuntimeTarget = "codex" | "claude_code" | "opencode";
export type CodexReasoningEffort = "low" | "medium" | "high";
export type CodexSandboxMode = "read-only" | "workspace-write" | "danger-full-access";
export type ClaudeModel = "sonnet" | "opus" | "haiku" | "inherit";
export type ClaudePermissionMode =
  | "default"
  | "acceptEdits"
  | "dontAsk"
  | "bypassPermissions"
  | "plan";
export type OpenCodePermission = "allow" | "ask" | "deny";

export type CodexExportOptions = {
  model?: string;
  model_reasoning_effort?: CodexReasoningEffort;
  sandbox_mode?: CodexSandboxMode;
};

export type ClaudeExportOptions = {
  model?: ClaudeModel;
  permissionMode?: ClaudePermissionMode;
};

export type OpenCodeExportOptions = {
  model?: string;
  permission?: OpenCodePermission;
};

export type ExportJob = {
  id: string;
  entity_type: "agent" | "team";
  entity_id: string;
  runtime_target: RuntimeTarget;
  status: "pending" | "completed" | "failed";
  result_url: string | null;
  error_message: string | null;
  created_by: string;
  created_at: string;
};

export type ExportJobListResponse = {
  items: ExportJob[];
  total: number;
  limit: number;
  offset: number;
};

export type AgentListResponse = {
  items: Agent[];
  total: number;
  limit: number;
  offset: number;
};

export type TeamListResponse = {
  items: Team[];
  total: number;
  limit: number;
  offset: number;
};

export type ReviewListResponse = {
  items: Review[];
  total: number;
  limit: number;
  offset: number;
};

export type AgentCreatePayload = {
  slug: string;
  title: string;
  short_description: string;
  full_description?: string;
  category?: string;
};

export type TeamCreatePayload = {
  slug: string;
  title: string;
  description?: string;
};

export type TeamItemCreatePayload = {
  agent_slug: string;
  role_name: string;
  order_index?: number;
  config_json?: Record<string, unknown>;
  is_required?: boolean;
};

export type ReviewCreatePayload = {
  rating: number;
  text?: string;
  works_as_expected?: boolean;
  outdated_flag?: boolean;
  unsafe_flag?: boolean;
};

export type ExportCreatePayload = {
  runtime_target: RuntimeTarget;
  codex?: CodexExportOptions;
  claude?: ClaudeExportOptions;
  opencode?: OpenCodeExportOptions;
};

export type AgentVersionCreatePayload = {
  version: string;
  changelog?: string;
  manifest_json?: Record<string, unknown>;
  compatibility_matrix?: Record<string, unknown>;
  export_targets?: RuntimeTarget[];
  install_instructions?: string;
};

export type FetchMyTeamsOptions = {
  status?: Team["status"];
};

function getApiBaseUrl(): string {
  return (
    process.env.API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    "http://localhost:8000/api/v1"
  );
}

export function resolveDownloadUrl(resultUrl: string): string {
  if (/^https?:\/\//i.test(resultUrl)) {
    return resultUrl;
  }
  const backendOrigin = getApiBaseUrl().replace(/\/api\/v1$/, "");
  const normalizedPath = resultUrl.startsWith("/") ? resultUrl : `/${resultUrl}`;
  return `${backendOrigin}${normalizedPath}`;
}

function extractErrorMessage(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string" && detail.length > 0) {
    return detail;
  }

  return null;
}

export async function fetchAgents(): Promise<AgentListResponse> {
  const response = await fetch(`${getApiBaseUrl()}/agents`, { cache: "no-store" });

  if (!response.ok) {
    throw new Error("Failed to fetch agents list.");
  }

  return response.json() as Promise<AgentListResponse>;
}

export async function fetchAgent(slug: string): Promise<Agent> {
  const response = await fetch(`${getApiBaseUrl()}/agents/${slug}`, { cache: "no-store" });

  if (!response.ok) {
    throw new Error("Failed to fetch agent details.");
  }

  return response.json() as Promise<Agent>;
}

export async function fetchTeams(): Promise<TeamListResponse> {
  const response = await fetch(`${getApiBaseUrl()}/teams`, { cache: "no-store" });

  if (!response.ok) {
    throw new Error("Failed to fetch teams list.");
  }

  return response.json() as Promise<TeamListResponse>;
}

export async function fetchTeam(slug: string): Promise<TeamDetails> {
  const response = await fetch(`${getApiBaseUrl()}/teams/${slug}`, { cache: "no-store" });

  if (!response.ok) {
    throw new Error("Failed to fetch team details.");
  }

  return response.json() as Promise<TeamDetails>;
}

export async function fetchMyTeams(
  token: string,
  options: FetchMyTeamsOptions = {}
): Promise<TeamListResponse> {
  const params = new URLSearchParams({ limit: "100" });
  if (options.status) {
    params.set("status", options.status);
  }

  const response = await fetch(`${getApiBaseUrl()}/me/teams?${params.toString()}`, {
    headers: {
      Authorization: `Bearer ${token}`
    },
    cache: "no-store"
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to fetch your teams.");
  }

  return json as TeamListResponse;
}

export async function fetchHealth(): Promise<{ status: string }> {
  const response = await fetch(`${getApiBaseUrl().replace(/\/api\/v1$/, "")}/healthz`, {
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error("Backend is unavailable.");
  }

  return response.json() as Promise<{ status: string }>;
}

export async function createAgent(payload: AgentCreatePayload, token: string): Promise<Agent> {
  const response = await fetch(`${getApiBaseUrl()}/agents`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to create agent.");
  }

  return json as Agent;
}

export async function publishAgent(slug: string, token: string): Promise<Agent> {
  const response = await fetch(`${getApiBaseUrl()}/agents/${slug}/publish`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    }
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to publish agent.");
  }

  return json as Agent;
}

export async function createTeam(payload: TeamCreatePayload, token: string): Promise<Team> {
  const response = await fetch(`${getApiBaseUrl()}/teams`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to create team.");
  }

  return json as Team;
}

export async function publishTeam(slug: string, token: string): Promise<Team> {
  const response = await fetch(`${getApiBaseUrl()}/teams/${slug}/publish`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    }
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to publish team.");
  }

  return json as Team;
}

export async function addTeamItem(
  slug: string,
  payload: TeamItemCreatePayload,
  token: string
): Promise<TeamDetails> {
  const response = await fetch(`${getApiBaseUrl()}/teams/${slug}/items`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to add team item.");
  }

  return json as TeamDetails;
}

export async function fetchAgentReviews(slug: string): Promise<ReviewListResponse> {
  const response = await fetch(`${getApiBaseUrl()}/agents/${slug}/reviews`, { cache: "no-store" });

  if (!response.ok) {
    throw new Error("Failed to fetch agent reviews.");
  }

  return response.json() as Promise<ReviewListResponse>;
}

export async function createAgentReview(
  slug: string,
  payload: ReviewCreatePayload,
  token: string
): Promise<Review> {
  const response = await fetch(`${getApiBaseUrl()}/agents/${slug}/reviews`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to create review.");
  }

  return json as Review;
}

export async function createAgentExport(
  slug: string,
  payload: ExportCreatePayload,
  token: string
): Promise<ExportJob> {
  const response = await fetch(`${getApiBaseUrl()}/exports/agents/${slug}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to export agent.");
  }

  return json as ExportJob;
}

export async function createAgentVersion(
  slug: string,
  payload: AgentVersionCreatePayload,
  token: string
): Promise<void> {
  const response = await fetch(`${getApiBaseUrl()}/agents/${slug}/versions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to create agent version.");
  }
}

export async function fetchAgentExports(
  slug: string,
  token: string,
  options: { limit?: number; offset?: number } = {}
): Promise<ExportJobListResponse> {
  const params = new URLSearchParams();
  params.set("limit", String(options.limit ?? 10));
  params.set("offset", String(options.offset ?? 0));

  const response = await fetch(`${getApiBaseUrl()}/exports/agents/${slug}?${params.toString()}`, {
    headers: {
      Authorization: `Bearer ${token}`
    },
    cache: "no-store"
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to fetch agent exports.");
  }

  return json as ExportJobListResponse;
}

export async function fetchTeamReviews(slug: string): Promise<ReviewListResponse> {
  const response = await fetch(`${getApiBaseUrl()}/teams/${slug}/reviews`, { cache: "no-store" });

  if (!response.ok) {
    throw new Error("Failed to fetch team reviews.");
  }

  return response.json() as Promise<ReviewListResponse>;
}

export async function createTeamReview(
  slug: string,
  payload: ReviewCreatePayload,
  token: string
): Promise<Review> {
  const response = await fetch(`${getApiBaseUrl()}/teams/${slug}/reviews`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to create review.");
  }

  return json as Review;
}

export async function createTeamExport(
  slug: string,
  payload: ExportCreatePayload,
  token: string
): Promise<ExportJob> {
  const response = await fetch(`${getApiBaseUrl()}/exports/teams/${slug}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to export team.");
  }

  return json as ExportJob;
}

export async function fetchTeamExports(
  slug: string,
  token: string,
  options: { limit?: number; offset?: number } = {}
): Promise<ExportJobListResponse> {
  const params = new URLSearchParams();
  params.set("limit", String(options.limit ?? 10));
  params.set("offset", String(options.offset ?? 0));

  const response = await fetch(`${getApiBaseUrl()}/exports/teams/${slug}?${params.toString()}`, {
    headers: {
      Authorization: `Bearer ${token}`
    },
    cache: "no-store"
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to fetch team exports.");
  }

  return json as ExportJobListResponse;
}

export async function fetchExportJob(exportId: string, token: string): Promise<ExportJob> {
  const response = await fetch(`${getApiBaseUrl()}/exports/${exportId}`, {
    headers: {
      Authorization: `Bearer ${token}`
    },
    cache: "no-store"
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to fetch export job.");
  }

  return json as ExportJob;
}
