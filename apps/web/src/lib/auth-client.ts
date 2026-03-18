export type AuthUser = {
  id: string;
  email: string;
  display_name: string;
  role: "user" | "moderator" | "admin";
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type AuthTokenResponse = {
  access_token: string;
  token_type: "bearer";
  user: AuthUser;
};

const ACCESS_TOKEN_KEY = "team_agent_platform_access_token";
export const ACCESS_TOKEN_COOKIE_NAME = "team_agent_platform_access_token";

function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
}

function extractErrorMessage(payload: unknown): string | null {
  if (typeof payload === "string") {
    const normalized = payload.trim();
    return normalized.length > 0 ? normalized : null;
  }

  if (!payload || typeof payload !== "object") {
    return null;
  }

  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string" && detail.length > 0) {
    return detail;
  }

  return null;
}

async function readResponsePayload(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
  document.cookie = `${ACCESS_TOKEN_COOKIE_NAME}=${encodeURIComponent(token)}; Path=/; SameSite=Lax`;
}

export function clearAccessToken(): void {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  document.cookie = `${ACCESS_TOKEN_COOKIE_NAME}=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax`;
}

export async function registerWithPassword(payload: {
  email: string;
  password: string;
  display_name: string;
}, options?: {
  fallbackMessage?: string;
}): Promise<AuthTokenResponse> {
  const response = await fetch(`${getApiBaseUrl()}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  const json = await readResponsePayload(response);

  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? options?.fallbackMessage ?? "Registration failed.");
  }

  return json as AuthTokenResponse;
}

export async function loginWithPassword(payload: {
  email: string;
  password: string;
}, options?: {
  fallbackMessage?: string;
}): Promise<AuthTokenResponse> {
  const response = await fetch(`${getApiBaseUrl()}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  const json = await readResponsePayload(response);

  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? options?.fallbackMessage ?? "Login failed.");
  }

  return json as AuthTokenResponse;
}

export async function fetchCurrentUser(token: string): Promise<AuthUser> {
  const response = await fetch(`${getApiBaseUrl()}/me`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store"
  });

  const json = await readResponsePayload(response);

  if (!response.ok) {
    throw new Error(extractErrorMessage(json) ?? "Unauthorized.");
  }

  return json as AuthUser;
}
