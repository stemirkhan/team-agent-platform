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
