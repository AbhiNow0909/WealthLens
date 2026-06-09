import { createClient } from "./supabase-browser";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function getAuthHeaders(): Promise<Record<string, string>> {
  const supabase = createClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...headers, ...init?.headers },
  });
  if (!res.ok) {
    const error = await res.text();
    throw new Error(error || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// --- Portfolio ---
export const getHoldings = () => apiFetch<Holding[]>("/portfolio/holdings");
export const getPortfolioSummary = () => apiFetch<PortfolioSummary>("/portfolio/summary");

// --- Analytics ---
export const getFundAnalytics = (isin: string) =>
  apiFetch<FundMetrics>(`/analytics/${isin}`);
export const compareFunds = (isins: string[]) =>
  apiFetch<FundMetrics[]>(`/analytics/compare?isins=${isins.join(",")}`);
export const getTrailingReturns = () =>
  apiFetch<TrailingReturnsRow[]>("/analytics/trailing-returns");

// --- Agent ---
export const runAgent = (prompt: string) =>
  apiFetch<AgentResponse>("/agent/run", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });

// --- Types ---
export interface Holding {
  id: string;
  isin: string;
  scheme_name: string;
  amfi_code: string;
  units_held: number;
  average_nav: number;
  current_nav: number;
  current_value: number;
  invested_value: number;
}

export interface PortfolioSummary {
  total_value: number;
  total_invested: number;
  total_gain: number;
  total_gain_pct: number;
  xirr: number;
  allocation: { name: string; value: number }[];
}

export interface FundMetrics {
  isin: string;
  scheme_name: string;
  xirr: number;
  trailing_1w: number;
  trailing_1m: number;
  trailing_3m: number;
  trailing_6m: number;
  trailing_1y: number;
  trailing_3y: number;
  trailing_5y: number;
  alpha: number;
  beta: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  expense_ratio: number;
}

export interface TrailingReturnsRow {
  isin: string;
  name: string;
  "1w": number;
  "1m": number;
  "3m": number;
  "6m": number;
  "1y": number;
  "3y": number;
  "5y": number;
}

export interface AgentResponse {
  response_text: string;
  export_url: string | null;
  report_id: string;
}
