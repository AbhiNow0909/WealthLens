"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getHoldings,
  getFundAnalytics,
  getRollingReturns,
  getTrailingReturns,
  type Holding,
  type FundMetrics,
  type RollingReturnPoint,
  type TrailingReturnsRow,
} from "@/lib/api";
import { formatCompactCurrency, formatPercent } from "@/lib/formatters";
import RollingReturnsChart from "@/components/charts/RollingReturnsChart";
import TrailingReturnsTable from "@/components/charts/TrailingReturnsTable";

export default function FundDetailClient({ isin }: { isin: string }) {
  const [holding, setHolding] = useState<Holding | null>(null);
  const [metrics, setMetrics] = useState<FundMetrics | null>(null);
  const [rolling, setRolling] = useState<RollingReturnPoint[]>([]);
  const [trailing, setTrailing] = useState<TrailingReturnsRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [holdings, m, t] = await Promise.all([
          getHoldings(),
          getFundAnalytics(isin),
          getTrailingReturns(),
        ]);
        setHolding(holdings.find((h) => h.isin === isin) ?? null);
        setMetrics(m);
        setTrailing(t);
        getRollingReturns(isin).then(setRolling).catch(() => setRolling([]));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load fund");
      } finally {
        setLoading(false);
      }
    })();
  }, [isin]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--bg)] p-6">
        <div className="max-w-7xl mx-auto space-y-4">
          <div className="h-8 w-64 bg-[var(--surface)] rounded animate-pulse" />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-20 bg-[var(--surface)] rounded-xl animate-pulse" />
            ))}
          </div>
          <div className="h-72 bg-[var(--surface)] rounded-xl animate-pulse" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-[var(--bg)] flex flex-col items-center justify-center gap-3">
        <p className="text-[var(--loss)] text-sm">{error}</p>
        <Link href="/dashboard" className="text-[var(--accent)] text-sm">
          ← Back to portfolio
        </Link>
      </div>
    );
  }

  const gain = (holding?.current_value ?? 0) - (holding?.invested_value ?? 0);
  const gainPct = (holding?.invested_value ?? 0) > 0 ? (gain / holding!.invested_value) * 100 : 0;
  const name = holding?.scheme_name ?? metrics?.scheme_name ?? isin;

  return (
    <div className="min-h-screen bg-[var(--bg)]">
      <nav className="border-b border-[var(--border)] px-6 py-4 flex items-center justify-between">
        <Link href="/dashboard" className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] text-sm transition-colors">
          ← Portfolio
        </Link>
        <span className="text-[var(--text-primary)] font-semibold tracking-tight">WealthLens</span>
      </nav>

      <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-xl font-semibold text-[var(--text-primary)] leading-tight">{name}</h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1 tabular-nums">{isin}</p>
        </div>

        {/* Value cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Current Value" value={formatCompactCurrency(holding?.current_value ?? 0)} />
          <StatCard label="Invested" value={formatCompactCurrency(holding?.invested_value ?? 0)} />
          <StatCard
            label="Gain"
            value={formatCompactCurrency(gain)}
            sub={formatPercent(gainPct)}
            tone={gain >= 0 ? "gain" : "loss"}
          />
          <StatCard
            label="XIRR"
            value={metrics?.xirr != null ? formatPercent(metrics.xirr) : "—"}
            tone={(metrics?.xirr ?? 0) >= 0 ? "gain" : "loss"}
          />
        </div>

        {/* Risk metrics grid */}
        <div>
          <h2 className="text-sm font-medium text-[var(--text-primary)] mb-3">Risk & Return Metrics</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <MetricCell label="Alpha" value={metrics?.alpha != null ? formatPercent(metrics.alpha) : "—"} />
            <MetricCell label="Beta" value={fmtRatio(metrics?.beta)} />
            <MetricCell label="Sharpe" value={fmtRatio(metrics?.sharpe_ratio)} />
            <MetricCell label="Sortino" value={fmtRatio(metrics?.sortino_ratio)} />
            <MetricCell label="Max Drawdown" value={metrics?.max_drawdown != null ? formatPercent(metrics.max_drawdown) : "—"} />
            <MetricCell label="Expense Ratio" value={metrics?.expense_ratio ? `${metrics.expense_ratio.toFixed(2)}%` : "—"} />
          </div>
        </div>

        {/* Rolling returns chart */}
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5">
          <h2 className="text-sm font-medium text-[var(--text-primary)] mb-4">Rolling 1-Year Returns</h2>
          <RollingReturnsChart data={rolling} />
        </div>

        {/* Trailing returns table */}
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5">
          <h2 className="text-sm font-medium text-[var(--text-primary)] mb-4">
            Trailing Returns — all funds
          </h2>
          <TrailingReturnsTable data={trailing} highlightIsin={isin} />
        </div>
      </div>
    </div>
  );
}

function fmtRatio(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return v.toFixed(2);
}

function StatCard({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "gain" | "loss";
}) {
  const toneClass = tone === "gain" ? "text-[var(--gain)]" : tone === "loss" ? "text-[var(--loss)]" : "text-[var(--text-primary)]";
  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl px-5 py-4">
      <p className="text-[var(--text-secondary)] text-xs mb-1">{label}</p>
      <p className={`tabular-nums text-lg font-semibold ${toneClass}`}>{value}</p>
      {sub && <p className={`tabular-nums text-xs mt-0.5 ${toneClass}`}>{sub}</p>}
    </div>
  );
}

function MetricCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl px-4 py-3">
      <p className="text-[var(--text-secondary)] text-xs mb-1">{label}</p>
      <p className="tabular-nums text-base font-semibold text-[var(--text-primary)]">{value}</p>
    </div>
  );
}
