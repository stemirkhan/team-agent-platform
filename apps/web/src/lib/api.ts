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
  manifest_json: Record<string, unknown> | null;
  source_archive_url: string | null;
  compatibility_matrix: Record<string, unknown> | null;
  export_targets: RuntimeTarget[] | null;
  install_instructions: string | null;
  skills: AgentSkill[];
  markdown_files: AgentMarkdownFile[];
};

export type RuntimeTarget = "codex";
export type CodexReasoningEffort = "low" | "medium" | "high";
export type CodexSandboxMode = "read-only" | "workspace-write" | "danger-full-access";
export type HostToolStatus = "ready" | "missing" | "outdated" | "not_authenticated" | "error";
export type HostExecutionSource = "host_executor";
export type RunStatus =
  | "queued"
  | "preparing"
  | "cloning_repo"
  | "materializing_team"
  | "running_setup"
  | "starting_codex"
  | "running"
  | "running_checks"
  | "committing"
  | "pushing"
  | "creating_pr"
  | "completed"
  | "failed"
  | "cancelled";
export type RunEventType = "status" | "error" | "note";

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
  agent_slug: string;
  agent_title: string;
  agent_short_description: string;
  role_name: string;
  order_index: number;
  config_json: Record<string, unknown> | null;
  is_required: boolean;
};

export type TeamDetails = Team & {
  items: TeamItem[];
};

export type AgentSkill = {
  slug: string;
  content: string;
  description?: string | null;
};

export type AgentMarkdownFile = {
  path: string;
  content: string;
};

export type CodexExportOptions = {
  model?: string;
  model_reasoning_effort?: CodexReasoningEffort;
  sandbox_mode?: CodexSandboxMode;
};

export type HostToolDiagnostics = {
  name: string;
  found: boolean;
  path: string | null;
  version: string | null;
  minimum_version: string;
  version_ok: boolean;
  auth_required: boolean;
  auth_ok: boolean | null;
  status: HostToolStatus;
  message: string;
  remediation_steps: string[];
};

export type HostExecutorContext = {
  user: string;
  home: string;
  cwd: string;
  containerized: boolean;
  container_runtime: string | null;
};

export type HostDiagnosticsSnapshot = {
  generated_at: string;
  ready: boolean;
  pty_supported: boolean;
  executor_context: HostExecutorContext;
  tools: {
    git: HostToolDiagnostics;
    gh: HostToolDiagnostics;
    codex: HostToolDiagnostics;
  };
  warnings: string[];
};

export type HostExecutionReadiness = {
  generated_at: string;
  execution_source: HostExecutionSource;
  effective_ready: boolean;
  host_executor_url: string | null;
  host_executor_reachable: boolean;
  host_executor_error: string | null;
  host_executor: HostDiagnosticsSnapshot | null;
};

export type Run = {
  id: string;
  team_id: string | null;
  team_slug: string;
  team_title: string;
  runtime_target: "codex";
  repo_owner: string;
  repo_name: string;
  repo_full_name: string;
  base_branch: string;
  working_branch: string | null;
  issue_number: number | null;
  issue_title: string | null;
  issue_url: string | null;
  title: string;
  summary: string | null;
  task_text: string | null;
  runtime_config_json: Record<string, unknown> | null;
  workspace_id: string | null;
  workspace_path: string | null;
  repo_path: string | null;
  status: RunStatus;
  error_message: string | null;
  pr_url: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
  run_report: RunReport | null;
};

export type Workspace = {
  id: string;
  repo_owner: string;
  repo_name: string;
  repo_full_name: string;
  remote_url: string;
  workspace_path: string;
  repo_path: string;
  base_branch: string;
  working_branch: string;
  current_branch: string | null;
  upstream_branch: string | null;
  status: "prepared" | "committed" | "pushed" | "pull_request_created";
  has_changes: boolean;
  changed_files: string[];
  last_commit_sha: string | null;
  last_commit_message: string | null;
  committed_at: string | null;
  pushed_at: string | null;
  pull_request_number: number | null;
  pull_request_url: string | null;
  created_at: string;
  updated_at: string;
};

export type RunEvent = {
  id: string;
  run_id: string;
  event_type: RunEventType;
  payload_json: Record<string, unknown> | null;
  created_at: string;
};

export type RunReportPhaseKey = "preparation" | "setup" | "codex" | "checks" | "git_pr";
export type RunReportPhaseStatus =
  | "not_started"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | "not_available";

export type RunReportCommand = {
  command: string;
  exit_code: number;
  succeeded: boolean;
  output: string | null;
  started_at: string | null;
  finished_at: string | null;
};

export type RunReportPhase = {
  key: RunReportPhaseKey;
  order: number;
  status: RunReportPhaseStatus;
  description: string | null;
  first_event_at: string | null;
  last_event_at: string | null;
  commands: RunReportCommand[];
  meta: Record<string, unknown>;
};

export type RunReport = {
  phases: RunReportPhase[];
};

export type RunListResponse = {
  items: Run[];
  total: number;
  limit: number;
  offset: number;
};

export type RunEventListResponse = {
  items: RunEvent[];
  total: number;
};

export type RunCreatePayload = {
  team_slug: string;
  repo_owner: string;
  repo_name: string;
  base_branch?: string;
  issue_number?: number;
  task_text?: string;
  title?: string;
  summary?: string;
  codex?: CodexExportOptions;
};

export type FetchRunsOptions = {
  limit?: number;
  offset?: number;
  status?: RunStatus;
};

export type CodexSessionStatus = "running" | "completed" | "failed" | "cancelled";

export type CodexSessionRead = {
  run_id: string;
  workspace_id: string;
  repo_path: string;
  command: string[];
  status: CodexSessionStatus;
  pid: number | null;
  exit_code: number | null;
  error_message: string | null;
  summary_text: string | null;
  started_at: string;
  finished_at: string | null;
  last_output_offset: number;
};

export type CodexTerminalChunk = {
  offset: number;
  text: string;
  created_at: string;
};

export type CodexSessionEventsResponse = {
  session: CodexSessionRead;
  items: CodexTerminalChunk[];
  next_offset: number;
};

export type GitHubRepo = {
  owner: string;
  name: string;
  full_name: string;
  description: string | null;
  url: string;
  ssh_url: string | null;
  is_private: boolean;
  visibility: string | null;
  default_branch: string | null;
  has_issues_enabled: boolean;
  viewer_permission: string | null;
  updated_at: string | null;
  pushed_at: string | null;
};

export type GitHubRepoListResponse = {
  items: GitHubRepo[];
  total: number;
  limit: number;
};

export type GitHubIssue = {
  number: number;
  title: string;
  body: string | null;
  state: string;
  url: string;
  author_login: string | null;
  labels: string[];
  comments_count: number;
  created_at: string | null;
  updated_at: string | null;
};

export type GitHubIssueComment = {
  id: string | null;
  author_login: string | null;
  body: string;
  url: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type GitHubIssueDetail = GitHubIssue & {
  comments: GitHubIssueComment[];
};

export type GitHubIssueListResponse = {
  items: GitHubIssue[];
  total: number;
  limit: number;
  state: string;
};

export type GitHubIssueCommentCreatePayload = {
  body: string;
};

export type GitHubIssueLabelsUpdatePayload = {
  labels: string[];
};

export type GitHubPull = {
  number: number;
  title: string;
  body: string | null;
  state: string;
  url: string;
  author_login: string | null;
  labels: string[];
  comments_count: number;
  is_draft: boolean;
  base_ref_name: string | null;
  head_ref_name: string | null;
  merge_state_status: string | null;
  mergeable: string | null;
  review_decision: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type GitHubPullListResponse = {
  items: GitHubPull[];
  total: number;
  limit: number;
  state: string;
};

export type GitHubPullCheck = {
  name: string;
  state: string;
  bucket: string | null;
  workflow: string | null;
  description: string | null;
  event: string | null;
  link: string | null;
  started_at: string | null;
  completed_at: string | null;
};

export type GitHubPullChecksSummary = {
  pass_count: number;
  fail_count: number;
  pending_count: number;
  skipping_count: number;
  cancel_count: number;
};

export type GitHubPullChecksResponse = {
  items: GitHubPullCheck[];
  total: number;
  summary: GitHubPullChecksSummary;
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

export type AgentCreatePayload = {
  slug: string;
  title: string;
  short_description: string;
  full_description?: string;
  category?: string;
};

export type AgentUpdatePayload = {
  title?: string;
  short_description?: string;
  full_description?: string | null;
  category?: string | null;
  manifest_json?: Record<string, unknown>;
  source_archive_url?: string | null;
  compatibility_matrix?: Record<string, unknown> | null;
  export_targets?: RuntimeTarget[] | null;
  install_instructions?: string | null;
  skills?: AgentSkill[];
  markdown_files?: AgentMarkdownFile[];
};

export type TeamCreatePayload = {
  slug: string;
  title: string;
  description?: string;
};

export type TeamUpdatePayload = {
  title?: string;
  description?: string | null;
};

export type TeamItemCreatePayload = {
  agent_slug: string;
  role_name: string;
  order_index?: number;
  config_json?: Record<string, unknown>;
  is_required?: boolean;
};

export type TeamItemUpdatePayload = {
  agent_slug?: string;
  role_name?: string;
  order_index?: number;
  config_json?: Record<string, unknown> | null;
  is_required?: boolean;
};

export type ExportCreatePayload = {
  runtime_target: RuntimeTarget;
  codex?: CodexExportOptions;
};

export type FetchMyTeamsOptions = {
  status?: Team["status"];
};

export type FetchAgentsOptions = {
  limit?: number;
  offset?: number;
  status?: Agent["status"];
  q?: string;
  category?: string;
};

export type FetchGitHubReposOptions = {
  owner?: string;
  q?: string;
  limit?: number;
};

export type FetchGitHubIssuesOptions = {
  state?: "open" | "closed" | "all";
  limit?: number;
};

export type FetchGitHubPullsOptions = {
  state?: "open" | "closed" | "merged" | "all";
  limit?: number;
};

function getApiBaseUrl(): string {
  return (
    process.env.API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    "http://localhost:8000/api/v1"
  );
}

function getBackendOrigin(): string {
  return getApiBaseUrl().replace(/\/api\/v1$/, "");
}

export function resolveDownloadUrl(resultUrl: string): string {
  if (/^https?:\/\//i.test(resultUrl)) {
    return resultUrl;
  }
  const backendOrigin = getBackendOrigin();
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

export async function fetchAgents(
  options: FetchAgentsOptions = {}
): Promise<AgentListResponse> {
  const params = new URLSearchParams();
  if (options.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  if (options.offset !== undefined) {
    params.set("offset", String(options.offset));
  }
  if (options.status) {
    params.set("status", options.status);
  }
  if (options.q) {
    params.set("q", options.q);
  }
  if (options.category) {
    params.set("category", options.category);
  }

  const query = params.size > 0 ? `?${params.toString()}` : "";
  const response = await fetch(`${getApiBaseUrl()}/agents${query}`, { cache: "no-store" });

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

export async function fetchHostDiagnostics(): Promise<HostDiagnosticsSnapshot> {
  const response = await fetch(`${getApiBaseUrl()}/host/diagnostics`, {
    cache: "no-store"
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to fetch host diagnostics.");
  }

  return json as HostDiagnosticsSnapshot;
}

export async function refreshHostDiagnostics(): Promise<HostDiagnosticsSnapshot> {
  const response = await fetch(`${getApiBaseUrl()}/host/diagnostics/refresh`, {
    method: "POST"
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to refresh host diagnostics.");
  }

  return json as HostDiagnosticsSnapshot;
}

export async function fetchHostReadiness(): Promise<HostExecutionReadiness> {
  const response = await fetch(`${getApiBaseUrl()}/host/readiness`, {
    cache: "no-store"
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to fetch host readiness.");
  }

  return json as HostExecutionReadiness;
}

export async function refreshHostReadiness(): Promise<HostExecutionReadiness> {
  const response = await fetch(`${getApiBaseUrl()}/host/readiness/refresh`, {
    method: "POST"
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to refresh host readiness.");
  }

  return json as HostExecutionReadiness;
}

export async function fetchRuns(
  token: string,
  options: FetchRunsOptions = {}
): Promise<RunListResponse> {
  const params = new URLSearchParams();
  params.set("limit", String(options.limit ?? 20));
  params.set("offset", String(options.offset ?? 0));
  if (options.status) {
    params.set("status", options.status);
  }

  const response = await fetch(`${getApiBaseUrl()}/runs?${params.toString()}`, {
    headers: {
      Authorization: `Bearer ${token}`
    },
    cache: "no-store"
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to fetch runs.");
  }

  return json as RunListResponse;
}

export async function fetchRun(runId: string, token: string): Promise<Run> {
  const response = await fetch(`${getApiBaseUrl()}/runs/${runId}`, {
    headers: {
      Authorization: `Bearer ${token}`
    },
    cache: "no-store"
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to fetch run.");
  }

  return json as Run;
}

export async function fetchWorkspace(workspaceId: string, token: string): Promise<Workspace> {
  const response = await fetch(`${getApiBaseUrl()}/workspaces/${workspaceId}`, {
    headers: {
      Authorization: `Bearer ${token}`
    },
    cache: "no-store"
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to fetch workspace.");
  }

  return json as Workspace;
}

export async function fetchRunEvents(runId: string, token: string): Promise<RunEventListResponse> {
  const response = await fetch(`${getApiBaseUrl()}/runs/${runId}/events`, {
    headers: {
      Authorization: `Bearer ${token}`
    },
    cache: "no-store"
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to fetch run events.");
  }

  return json as RunEventListResponse;
}

export async function createRun(payload: RunCreatePayload, token: string): Promise<Run> {
  const response = await fetch(`${getApiBaseUrl()}/runs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to create run.");
  }

  return json as Run;
}

export async function cancelRun(runId: string, token: string): Promise<Run> {
  const response = await fetch(`${getApiBaseUrl()}/runs/${runId}/cancel`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    }
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to cancel run.");
  }

  return json as Run;
}

export async function fetchRunTerminalSession(
  runId: string,
  token: string
): Promise<CodexSessionRead | null> {
  const response = await fetch(`${getApiBaseUrl()}/runs/${runId}/terminal/session`, {
    headers: {
      Authorization: `Bearer ${token}`
    },
    cache: "no-store"
  });

  if (response.status === 404) {
    return null;
  }

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to fetch terminal session.");
  }

  return json as CodexSessionRead;
}

export async function fetchRunTerminalEvents(
  runId: string,
  token: string,
  offset = 0
): Promise<CodexSessionEventsResponse | null> {
  const response = await fetch(`${getApiBaseUrl()}/runs/${runId}/terminal/events?offset=${offset}`, {
    headers: {
      Authorization: `Bearer ${token}`
    },
    cache: "no-store"
  });

  if (response.status === 404) {
    return null;
  }

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to fetch terminal events.");
  }

  return json as CodexSessionEventsResponse;
}

export function buildRunTerminalWebSocketUrl(runId: string, token: string): string {
  const backendOrigin = getBackendOrigin();
  const protocol = backendOrigin.startsWith("https://") ? "wss://" : "ws://";
  const host = backendOrigin.replace(/^https?:\/\//, "");
  return `${protocol}${host}/api/v1/runs/${encodeURIComponent(runId)}/terminal?token=${encodeURIComponent(token)}`;
}

export async function fetchGitHubRepos(
  options: FetchGitHubReposOptions = {}
): Promise<GitHubRepoListResponse> {
  const params = new URLSearchParams();
  if (options.owner) {
    params.set("owner", options.owner);
  }
  if (options.q) {
    params.set("q", options.q);
  }
  params.set("limit", String(options.limit ?? 30));

  const query = params.size > 0 ? `?${params.toString()}` : "";
  const response = await fetch(`${getApiBaseUrl()}/github/repos${query}`, {
    cache: "no-store"
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to fetch GitHub repositories.");
  }

  return json as GitHubRepoListResponse;
}

export async function fetchGitHubRepo(owner: string, repo: string): Promise<GitHubRepo> {
  const response = await fetch(`${getApiBaseUrl()}/github/repos/${owner}/${repo}`, {
    cache: "no-store"
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to fetch GitHub repository.");
  }

  return json as GitHubRepo;
}

export async function fetchGitHubRepoIssues(
  owner: string,
  repo: string,
  options: FetchGitHubIssuesOptions = {}
): Promise<GitHubIssueListResponse> {
  const params = new URLSearchParams();
  params.set("state", options.state ?? "open");
  params.set("limit", String(options.limit ?? 30));

  const response = await fetch(
    `${getApiBaseUrl()}/github/repos/${owner}/${repo}/issues?${params.toString()}`,
    {
      cache: "no-store"
    }
  );

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to fetch GitHub issues.");
  }

  return json as GitHubIssueListResponse;
}

export async function fetchGitHubIssue(
  owner: string,
  repo: string,
  number: number
): Promise<GitHubIssueDetail> {
  const response = await fetch(`${getApiBaseUrl()}/github/repos/${owner}/${repo}/issues/${number}`, {
    cache: "no-store"
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to fetch GitHub issue.");
  }

  return json as GitHubIssueDetail;
}

export async function fetchGitHubRepoPulls(
  owner: string,
  repo: string,
  options: FetchGitHubPullsOptions = {}
): Promise<GitHubPullListResponse> {
  const params = new URLSearchParams();
  params.set("state", options.state ?? "open");
  params.set("limit", String(options.limit ?? 30));

  const response = await fetch(
    `${getApiBaseUrl()}/github/repos/${owner}/${repo}/pulls?${params.toString()}`,
    {
      cache: "no-store"
    }
  );

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to fetch GitHub pull requests.");
  }

  return json as GitHubPullListResponse;
}

export async function fetchGitHubPull(
  owner: string,
  repo: string,
  number: number
): Promise<GitHubPull> {
  const response = await fetch(`${getApiBaseUrl()}/github/repos/${owner}/${repo}/pulls/${number}`, {
    cache: "no-store"
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to fetch GitHub pull request.");
  }

  return json as GitHubPull;
}

export async function fetchGitHubPullChecks(
  owner: string,
  repo: string,
  number: number
): Promise<GitHubPullChecksResponse> {
  const response = await fetch(
    `${getApiBaseUrl()}/github/repos/${owner}/${repo}/pulls/${number}/checks`,
    {
      cache: "no-store"
    }
  );

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to fetch GitHub pull request checks.");
  }

  return json as GitHubPullChecksResponse;
}

export async function createGitHubIssueComment(
  owner: string,
  repo: string,
  number: number,
  payload: GitHubIssueCommentCreatePayload
): Promise<GitHubIssueDetail> {
  const response = await fetch(`${getApiBaseUrl()}/github/repos/${owner}/${repo}/issues/${number}/comments`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to add GitHub issue comment.");
  }

  return json as GitHubIssueDetail;
}

export async function addGitHubIssueLabels(
  owner: string,
  repo: string,
  number: number,
  payload: GitHubIssueLabelsUpdatePayload
): Promise<GitHubIssueDetail> {
  const response = await fetch(`${getApiBaseUrl()}/github/repos/${owner}/${repo}/issues/${number}/labels`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to add GitHub issue labels.");
  }

  return json as GitHubIssueDetail;
}

export async function removeGitHubIssueLabel(
  owner: string,
  repo: string,
  number: number,
  labelName: string
): Promise<GitHubIssueDetail> {
  const response = await fetch(
    `${getApiBaseUrl()}/github/repos/${owner}/${repo}/issues/${number}/labels/${encodeURIComponent(labelName)}`,
    {
      method: "DELETE"
    }
  );

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to remove GitHub issue label.");
  }

  return json as GitHubIssueDetail;
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

export async function updateAgent(
  slug: string,
  payload: AgentUpdatePayload,
  token: string
): Promise<Agent> {
  const response = await fetch(`${getApiBaseUrl()}/agents/${slug}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to update agent.");
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

export async function updateTeam(
  slug: string,
  payload: TeamUpdatePayload,
  token: string
): Promise<TeamDetails> {
  const response = await fetch(`${getApiBaseUrl()}/teams/${slug}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to update team.");
  }

  return json as TeamDetails;
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

export async function updateTeamItem(
  slug: string,
  itemId: string,
  payload: TeamItemUpdatePayload,
  token: string
): Promise<TeamDetails> {
  const response = await fetch(`${getApiBaseUrl()}/teams/${slug}/items/${itemId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to update team item.");
  }

  return json as TeamDetails;
}

export async function deleteTeamItem(
  slug: string,
  itemId: string,
  token: string
): Promise<TeamDetails> {
  const response = await fetch(`${getApiBaseUrl()}/teams/${slug}/items/${itemId}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`
    }
  });

  const json = (await response.json()) as unknown;
  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Failed to delete team item.");
  }

  return json as TeamDetails;
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
