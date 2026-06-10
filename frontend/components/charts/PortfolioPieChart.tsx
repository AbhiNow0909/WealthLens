"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { formatCompactCurrency } from "@/lib/formatters";

interface Slice {
  name: string;
  value: number;
}

// Distinct hues that read well on the dark surface
const COLORS = [
  "#4F8EF7", "#22C55E", "#F59E0B", "#A855F7", "#EC4899", "#14B8A6",
  "#F97316", "#3B82F6", "#84CC16", "#06B6D4", "#8B5CF6", "#EAB308",
  "#10B981", "#F43F5E", "#6366F1", "#0EA5E9", "#D946EF", "#65A30D",
];

function CustomTooltip({
  active,
  payload,
  total,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number }>;
  total: number;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0];
  const pct = total > 0 ? ((d.value / total) * 100).toFixed(1) : "0";
  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-lg px-3 py-2 shadow-lg">
      <p className="text-xs text-[var(--text-primary)] max-w-[200px]">{d.name}</p>
      <p className="text-xs text-[var(--text-secondary)] tabular-nums mt-0.5">
        {formatCompactCurrency(d.value)} · {pct}%
      </p>
    </div>
  );
}

export default function PortfolioPieChart({ data }: { data: Slice[] }) {
  const sorted = [...data].filter((d) => d.value > 0).sort((a, b) => b.value - a.value);
  const total = sorted.reduce((s, d) => s + d.value, 0);

  if (sorted.length === 0) {
    return (
      <p className="text-sm text-[var(--text-secondary)] py-12 text-center">
        No allocation data yet.
      </p>
    );
  }

  return (
    <div className="flex flex-col md:flex-row items-center gap-6">
      <div className="w-full md:w-1/2 shrink-0" style={{ height: 240 }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={sorted}
              dataKey="value"
              nameKey="name"
              innerRadius={58}
              outerRadius={100}
              paddingAngle={1}
              stroke="none"
            >
              {sorted.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip total={total} />} />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Legend — scrollable list of every fund with colour, value and share */}
      <div className="w-full md:w-1/2 max-h-[240px] overflow-y-auto pr-1 space-y-2">
        {sorted.map((d, i) => {
          const pct = total > 0 ? ((d.value / total) * 100).toFixed(1) : "0";
          return (
            <div key={d.name} className="flex items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-2 min-w-0">
                <span
                  className="w-2.5 h-2.5 rounded-sm shrink-0"
                  style={{ backgroundColor: COLORS[i % COLORS.length] }}
                />
                <span className="text-[var(--text-secondary)] truncate">{d.name}</span>
              </div>
              <span className="text-[var(--text-primary)] tabular-nums shrink-0">{pct}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
