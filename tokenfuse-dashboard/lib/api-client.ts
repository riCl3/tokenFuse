import type {
  ProjectDashboardRow,
  ProjectCreate,
  ProjectCreatedResponse,
  ProjectResponse,
  UsageSummary,
} from "./api-types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// --- Auth token (JWT) ---
export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("tokenfuse_auth_token");
}

export function setAuthToken(token: string) {
  if (typeof window !== "undefined") {
    localStorage.setItem("tokenfuse_auth_token", token);
  }
}

export function clearAuthToken() {
  if (typeof window !== "undefined") {
    localStorage.removeItem("tokenfuse_auth_token");
  }
}

// --- Project API key (tfsk_) — legacy, kept for proxy usage ---
export function getApiKey(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("tokenfuse_api_key");
}

export function setApiKey(key: string) {
  if (typeof window !== "undefined") {
    localStorage.setItem("tokenfuse_api_key", key);
  }
}

export function clearApiKey() {
  if (typeof window !== "undefined") {
    localStorage.removeItem("tokenfuse_api_key");
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { skipAuth?: boolean } = {},
): Promise<T> {
  const { skipAuth, ...fetchOptions } = options;
  // Prefer JWT auth token over API key
  const token = skipAuth ? null : getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(fetchOptions.headers as Record<string, string> ?? {}),
  };

  const res = await fetch(`${API_BASE}${path}`, {
    ...fetchOptions,
    headers,
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }

  return res.json() as Promise<T>;
}

// --- Auth ---

export async function signup(email: string, password: string, displayName?: string): Promise<{ access_token: string }> {
  return request("/v1/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password, display_name: displayName }),
    skipAuth: true,
  } as RequestInit & { skipAuth?: boolean });
}

export async function login(email: string, password: string): Promise<{ access_token: string }> {
  return request("/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
    skipAuth: true,
  } as RequestInit & { skipAuth?: boolean });
}

export async function getMe(): Promise<{ id: number; email: string; display_name: string | null; is_active: boolean }> {
  return request("/v1/auth/me");
}

// --- Projects ---

export async function listProjects(): Promise<ProjectDashboardRow[]> {
  return request("/v1/projects");
}

export async function getProject(id: number): Promise<ProjectResponse> {
  return request(`/v1/projects/${id}`);
}

export async function createProject(
  data: ProjectCreate,
): Promise<ProjectCreatedResponse> {
  return request("/v1/projects", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// --- Usage ---

export async function getUsageSummary(
  projectId: number,
): Promise<UsageSummary> {
  return request(`/v1/usage/${projectId}`);
}

// --- Health ---

export async function checkHealth(): Promise<{ app: string; environment: string }> {
  return request("/health");
}

// --- Pricing (global) ---

export async function listPricing(): Promise<import("./api-types").PricingRow[]> {
  return request("/v1/pricing");
}

export async function createPricing(data: import("./api-types").PricingCreate): Promise<import("./api-types").PricingRow> {
  return request("/v1/pricing", { method: "POST", body: JSON.stringify(data) });
}

export async function updatePricing(model: string, data: import("./api-types").PricingUpdate): Promise<import("./api-types").PricingRow> {
  return request(`/v1/pricing/${encodeURIComponent(model)}`, { method: "PUT", body: JSON.stringify(data) });
}

export async function deletePricing(model: string): Promise<void> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  const res = await fetch(`${API_BASE}/v1/pricing/${encodeURIComponent(model)}`, { method: "DELETE", headers });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
}

// --- Project update ---

export async function updateProject(id: number, data: import("./api-types").ProjectUpdate): Promise<import("./api-types").ProjectResponse> {
  return request(`/v1/projects/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}
