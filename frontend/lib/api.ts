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
export const syncNavs = () => apiFetch<Record<string, unknown>>("/portfolio/sync-navs", { method: "POST" });
export const getNavHistory = () => apiFetch<Record<string, NavPoint[]>>("/portfolio/nav-history");

// --- Analytics ---
export const getFundAnalytics = (isin: string) =>
  apiFetch<FundMetrics>(`/analytics/${isin}`);
export const compareFunds = (isins: string[]) =>
  apiFetch<FundMetrics[]>(`/analytics/compare?isins=${isins.join(",")}`);
export const getTrailingReturns = () =>
  apiFetch<TrailingReturnsRow[]>("/analytics/trailing-returns");
export const getRollingReturns = (isin: string) =>
  apiFetch<RollingReturnPoint[]>(`/analytics/${isin}/rolling-returns`);

// --- Agent ---
export const runAgent = (prompt: string) =>
  apiFetch<AgentResponse>("/agent/run", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });

export type ExportFormat = "excel" | "word" | "ppt";
export const exportReport = (format: ExportFormat) =>
  apiFetch<ExportResult>("/agent/export", {
    method: "POST",
    body: JSON.stringify({ format }),
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

export interface NavPoint {
  nav_date: string;
  nav: number;
}

export interface FundMetrics {
  isin: string;
  scheme_name: string;
  xirr: number | null;
  trailing_1w: number | null;
  trailing_1m: number | null;
  trailing_3m: number | null;
  trailing_6m: number | null;
  trailing_1y: number | null;
  trailing_3y: number | null;
  trailing_5y: number | null;
  alpha: number | null;
  beta: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  treynor_ratio: number | null;
  max_drawdown: number | null;
  expense_ratio: number | null;
  turnover_ratio: number | null;
}

export interface TrailingReturnsRow {
  isin: string;
  name: string;
  "1w": number | null;
  "1m": number | null;
  "3m": number | null;
  "6m": number | null;
  "1y": number | null;
  "3y": number | null;
  "5y": number | null;
}

export interface RollingReturnPoint {
  date: string;
  value: number;
}

export interface AgentResponse {
  response_text: string;
  export_url: string | null;
  report_id: string;
}

export interface ExportResult {
  export_url: string | null;
  filename: string;
  format: string;
}
