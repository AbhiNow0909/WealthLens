"use client";

import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { FundMetrics } from "@/lib/api";

// Axes shown on the radar. Expense ratio is omitted (placeholder 0 → degenerate).
// For every axis here, a larger raw value is "stronger" (max_drawdown is signed,
// so -10% > -25% already means a shallower, better drawdown).
const AXES = [
  { key: "alpha", label: "Alpha" },
  { key: "beta", label: "Beta" },
  { key: "sharpe_ratio", label: "Sharpe" },
  { key: "sortino_ratio", label: "Sortino" },
  { key: "max_drawdown", label: "Drawdown" },
] as const;

function raw(f: FundMetrics, key: string): number {
  const v = (f as unknown as Record<string, number | null>)[key];
  return v == null ? 0 : v;
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-lg px-3 py-2 shadow-lg">
      <p className="text-xs text-[var(--text-primary)] mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="text-xs tabular-nums" style={{ color: p.color }}>
          {p.value} / 100
        </p>
      ))}
    </div>
  );
}

interface Props {
  funds: FundMetrics[];
  colors: string[];
}

export default function RiskRadarChart({ funds, colors }: Props) {
  if (funds.length === 0) return null;

  // Normalise each axis to 0–100 across the selected funds (best fund = 100).
  const data = AXES.map((axis) => {
    const values = funds.map((f) => raw(f, axis.key));
    const min = Math.min(...values);
    const max = Math.max(...values);
    const row: Record<string, number | string> = { metric: axis.label };
    funds.forEach((f) => {
      const v = raw(f, axis.key);
      const norm = max === min ? 60 : ((v - min) / (max - min)) * 100;
      row[f.isin] = Math.round(norm);
    });
    return row;
  });

  return (
    <ResponsiveContainer width="100%" height={360}>
      <RadarChart data={data} outerRadius="72%">
        <PolarGrid stroke="var(--border)" />
        <PolarAngleAxis dataKey="metric" tick={{ fill: "var(--text-secondary)", fontSize: 12 }} />
        {funds.map((f, i) => (
          <Radar
            key={f.isin}
            name={f.scheme_name}
            dataKey={f.isin}
            stroke={colors[i % colors.length]}
            fill={colors[i % colors.length]}
            fillOpacity={0.15}
            isAnimationActive
            animationDuration={600}
          />
        ))}
        <Tooltip content={<CustomTooltip />} />
      </RadarChart>
    </ResponsiveContainer>
  );
}
