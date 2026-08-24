// TokenFuse API Types — mirrors the backend Pydantic schemas

export interface ApiKeySummary {
  id: number;
  label: string | null;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
}

export interface ProjectResponse {
  id: number;
  name: string;
  monthly_budget_usd: string;
  warn_pct: number;
  fallback_model: string | null;
  custom_pricing: Record<string, { input: number; output: number }> | null;
  is_active: boolean;
  created_at: string;
  api_keys: ApiKeySummary[];
}

export interface ProjectCreatedResponse {
  project: ProjectResponse;
  api_key: string;
}

export interface ProjectCreate {
  name: string;
  monthly_budget_usd?: number | null;
  warn_pct?: number | null;
  fallback_model?: string | null;
  custom_pricing?: Record<string, { input: number; output: number }> | null;
}

export interface ProjectUpdate {
  name?: string | null;
  monthly_budget_usd?: number | null;
  warn_pct?: number | null;
  fallback_model?: string | null;
  custom_pricing?: Record<string, { input: number; output: number }> | null;
  is_active?: boolean | null;
}

export interface PricingRow {
  id: number;
  model: string;
  input_price: string;
  output_price: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PricingCreate {
  model: string;
  input_price: number;
  output_price: number;
}

export interface PricingUpdate {
  input_price?: number | null;
  output_price?: number | null;
  is_active?: boolean | null;
}

export interface ProjectDashboardRow {
  id: number;
  name: string;
  monthly_budget_usd: string;
  is_active: boolean;
  created_at: string;
  total_requests: number;
  total_cost_usd: string;
  total_tokens: number;
  window_used_units: number;
  window_budget_units: number;
  window_status: string;
}

export interface ModelUsageRow {
  model: string;
  requests: number;
  cost_usd: string;
  total_tokens: number;
}

export interface UsageSummary {
  project_id: number;
  project_name: string;
  totals: {
    total_requests: number;
    total_cost_usd: string;
    total_tokens: number;
  };
  by_model: ModelUsageRow[];
  last_24h_cost_usd: string;
  window_used_units: number;
  window_budget_units: number;
  window_status: string;
}
