"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { RollingReturnPoint } from "@/lib/api";

const ACCENT = "#4F8EF7";

function CustomTooltip({
  active,
  payload,
  label,
  windowLabel,
}: {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
  windowLabel: string;
}) {
  if (!active || !payload?.length) return null;
  const v = payload[0].value;
  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-lg px-3 py-2 shadow-lg">
      <p className="text-xs text-[var(--text-secondary)]">{label}</p>
      <p
        className={`text-xs tabular-nums mt-0.5 ${
          v >= 0 ? "text-[var(--gain)]" : "text-[var(--loss)]"
        }`}
      >
        {v >= 0 ? "+" : ""}
        {v.toFixed(2)}% ({windowLabel} rolling)
      </p>
    </div>
  );
}

export default function RollingReturnsChart({
  data,
  windowLabel = "1Y",
}: {
  data: RollingReturnPoint[];
  windowLabel?: string;
}) {
  if (!data || data.length < 2) {
    return (
      <p className="text-sm text-[var(--text-secondary)] py-12 text-center">
        Not enough price history for this rolling window.
      </p>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
        <defs>
          <linearGradient id="rollingFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={ACCENT} stopOpacity={0.35} />
            <stop offset="100%" stopColor={ACCENT} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="var(--border)" strokeOpacity={0.5} vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: "var(--border)" }}
          minTickGap={48}
          tickFormatter={(d: string) => d.slice(0, 7)}
        />
        <YAxis
          tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => `${v.toFixed(0)}%`}
          width={48}
        />
        <ReferenceLine y={0} stroke="var(--border)" />
        <Tooltip content={<CustomTooltip windowLabel={windowLabel} />} />
        <Area
          type="monotone"
          dataKey="value"
          stroke={ACCENT}
          strokeWidth={1.5}
          fill="url(#rollingFill)"
          isAnimationActive
          animationDuration={700}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
