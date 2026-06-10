"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  getHoldings,
  compareFunds,
  type Holding,
  type FundMetrics,
} from "@/lib/api";
import { formatPercent } from "@/lib/formatters";
import RiskRadarChart from "@/components/charts/RiskRadarChart";

// Shared palette — fund colour is consistent across chips, radar and table.
const COLORS = [
  "#4F8EF7", "#22C55E", "#F59E0B", "#A855F7", "#EC4899", "#14B8A6", "#F97316", "#3B82F6",
];

function fmtRatio(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return v.toFixed(2);
}

const METRIC_ROWS: { label: string; fmt: (m: FundMetrics) => string }[] = [
  { label: "Alpha", fmt: (m) => (m.alpha != null ? formatPercent(m.alpha) : "—") },
  { label: "Beta", fmt: (m) => fmtRatio(m.beta) },
  { label: "Sharpe Ratio", fmt: (m) => fmtRatio(m.sharpe_ratio) },
  { label: "Sortino Ratio", fmt: (m) => fmtRatio(m.sortino_ratio) },
  { label: "Max Drawdown", fmt: (m) => (m.max_drawdown != null ? formatPercent(m.max_drawdown) : "—") },
  { label: "Expense Ratio", fmt: (m) => (m.expense_ratio ? `${m.expense_ratio.toFixed(2)}%` : "—") },
];

export default function CompareClient() {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [metrics, setMetrics] = useState<FundMetrics[]>([]);
  const [loading, setLoading] = useState(true);

  // Load the user's funds; default-select the first three.
  useEffect(() => {
    (async () => {
      try {
        const h = await getHoldings();
        setHoldings(h);
        setSelected(new Set(h.slice(0, 3).map((x) => x.isin)));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Stable, holdings-ordered list of the selected funds (drives colour assignment).
  const selectedList = useMemo(
    () => holdings.filter((h) => selected.has(h.isin)),
    [holdings, selected],
  );

  const colorFor = (isin: string) => {
    const idx = selectedList.findIndex((h) => h.isin === isin);
    return COLORS[(idx < 0 ? 0 : idx) % COLORS.length];
  };

  // Fetch metrics whenever the selection changes. When nothing is selected we
  // leave `metrics` as-is — the render shows a prompt instead, so it isn't seen.
  useEffect(() => {
    const isins = selectedList.map((h) => h.isin);
    if (isins.length === 0) return;
    compareFunds(isins)
      .then((m) => {
        // Re-order to match selectedList so colours line up
        const byIsin = new Map(m.map((x) => [x.isin, x]));
        setMetrics(isins.map((i) => byIsin.get(i)).filter(Boolean) as FundMetrics[]);
      })
      .catch(() => setMetrics([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [Array.from(selected).sort().join(",")]);

  function toggle(isin: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(isin)) next.delete(isin);
      else next.add(isin);
      return next;
    });
  }

  const radarColors = metrics.map((m) => colorFor(m.isin));

  return (
    <div className="min-h-screen bg-[var(--bg)]">
      <nav className="border-b border-[var(--border)] px-6 py-4 flex items-center justify-between">
        <span className="text-[var(--text-primary)] font-semibold tracking-tight">WealthLens</span>
        <div className="flex items-center gap-6 text-sm text-[var(--text-secondary)]">
          <Link href="/dashboard" className="hover:text-[var(--text-primary)] transition-colors">Portfolio</Link>
          <Link href="/compare" className="text-[var(--text-primary)]">Compare</Link>
          <Link href="/assistant" className="hover:text-[var(--text-primary)] transition-colors">Assistant</Link>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        <div>
          <h1 className="text-xl font-semibold text-[var(--text-primary)] mb-1">Risk Comparison</h1>
          <p className="text-[var(--text-secondary)] text-sm">
            Select funds to compare their risk and return profiles side by side.
          </p>
        </div>

        {loading ? (
          <div className="h-72 bg-[var(--surface)] rounded-xl animate-pulse" />
        ) : holdings.length === 0 ? (
          <p className="text-[var(--text-secondary)] text-sm">
            No funds yet. Upload a CAS statement from the{" "}
            <Link href="/dashboard" className="text-[var(--accent)]">portfolio page</Link>.
          </p>
        ) : (
          <>
            {/* Fund selector */}
            <div className="flex flex-wrap gap-2">
              {holdings.map((h) => {
                const on = selected.has(h.isin);
                return (
                  <button
                    key={h.isin}
                    onClick={() => toggle(h.isin)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs transition-colors ${
                      on
                        ? "border-[var(--accent)] bg-[var(--accent)]/10 text-[var(--text-primary)]"
                        : "border-[var(--border)] text-[var(--text-secondary)] hover:border-[var(--text-secondary)]"
                    }`}
                  >
                    {on && (
                      <span
                        className="w-2 h-2 rounded-full shrink-0"
                        style={{ backgroundColor: colorFor(h.isin) }}
                      />
                    )}
                    <span className="max-w-[220px] truncate">{h.scheme_name}</span>
                  </button>
                );
              })}
            </div>

            {selectedList.length === 0 ? (
              <p className="text-[var(--text-secondary)] text-sm py-12 text-center">
                Select at least one fund to compare.
              </p>
            ) : metrics.length === 0 ? (
              <div className="h-72 bg-[var(--surface)] rounded-xl animate-pulse" />
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Radar */}
                <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5">
                  <h2 className="text-sm font-medium text-[var(--text-primary)] mb-1">Risk Profile</h2>
                  <p className="text-xs text-[var(--text-secondary)] mb-4">
                    Normalised 0–100 across selected funds (higher = stronger on that axis).
                  </p>
                  <RiskRadarChart funds={metrics} colors={radarColors} />
                </div>

                {/* Side-by-side metrics table */}
                <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5 overflow-x-auto">
                  <h2 className="text-sm font-medium text-[var(--text-primary)] mb-4">Metrics</h2>
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="text-xs border-b border-[var(--border)]">
                        <th className="text-left px-3 py-2 font-medium text-[var(--text-secondary)]">Metric</th>
                        {metrics.map((m) => (
                          <th key={m.isin} className="text-right px-3 py-2 font-medium">
                            <div className="flex items-center justify-end gap-2">
                              <span
                                className="w-2 h-2 rounded-full shrink-0"
                                style={{ backgroundColor: colorFor(m.isin) }}
                              />
                              <span className="text-[var(--text-primary)] max-w-[120px] truncate" title={m.scheme_name}>
                                {m.scheme_name}
                              </span>
                            </div>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {METRIC_ROWS.map((row) => (
                        <tr key={row.label} className="border-b border-[var(--border)]">
                          <td className="px-3 py-2.5 text-[var(--text-secondary)]">{row.label}</td>
                          {metrics.map((m) => (
                            <td key={m.isin} className="px-3 py-2.5 text-right tabular-nums text-[var(--text-primary)]">
                              {row.fmt(m)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
