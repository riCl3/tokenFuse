import type {
  ProjectDashboardRow,
  ProjectCreate,
  ProjectCreatedResponse,
  ProjectResponse,
  UsageSummary,
} from "./api-types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Simple token storage — in production, use a proper auth flow
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
  const apiKey = skipAuth ? null : getApiKey();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
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
  // Bootstrap: POST /v1/projects is intentionally unauthenticated, so we
  // must not send a stale/invalid Authorization header that would confuse
  // the server logs with a spurious 401.
  return request("/v1/projects", {
    method: "POST",
    body: JSON.stringify(data),
    skipAuth: true,
  } as RequestInit & { skipAuth?: boolean });
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
  const apiKey = getApiKey();
  const headers: Record<string, string> = {
    ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
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
