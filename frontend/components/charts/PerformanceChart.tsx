"use client";

import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { PerformancePoint } from "@/lib/api";
import { formatCompactCurrency } from "@/lib/formatters";

const VALUE_COLOR = "#4F8EF7"; // accent — current value
const INVESTED_COLOR = "#94A3B8"; // muted — amount invested

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ dataKey: string; value: number }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const value = payload.find((p) => p.dataKey === "value")?.value ?? 0;
  const invested = payload.find((p) => p.dataKey === "invested")?.value ?? 0;
  const gain = value - invested;
  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-lg px-3 py-2 shadow-lg space-y-0.5">
      <p className="text-xs text-[var(--text-secondary)]">{label}</p>
      <p className="text-xs tabular-nums text-[var(--text-primary)]">
        Value {formatCompactCurrency(value)}
      </p>
      <p className="text-xs tabular-nums text-[var(--text-secondary)]">
        Invested {formatCompactCurrency(invested)}
      </p>
      <p
        className={`text-xs tabular-nums ${gain >= 0 ? "text-[var(--gain)]" : "text-[var(--loss)]"}`}
      >
        Gain {formatCompactCurrency(gain)}
      </p>
    </div>
  );
}

export default function PerformanceChart({ data }: { data: PerformancePoint[] }) {
  if (!data || data.length < 2) {
    return (
      <p className="text-sm text-[var(--text-secondary)] py-12 text-center">
        Not enough data for this range. Upload a detailed CAS and refresh prices.
      </p>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 4 }}>
        <defs>
          <linearGradient id="valueFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={VALUE_COLOR} stopOpacity={0.3} />
            <stop offset="100%" stopColor={VALUE_COLOR} stopOpacity={0} />
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
          domain={["auto", "auto"]}
          tickFormatter={(v: number) => formatCompactCurrency(v)}
          width={64}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          wrapperStyle={{ fontSize: 12 }}
          formatter={(v) => (v === "value" ? "Value" : "Invested")}
        />
        <Area
          type="monotone"
          dataKey="value"
          stroke={VALUE_COLOR}
          strokeWidth={1.5}
          fill="url(#valueFill)"
          isAnimationActive
          animationDuration={600}
        />
        <Line
          type="monotone"
          dataKey="invested"
          stroke={INVESTED_COLOR}
          strokeWidth={1.5}
          strokeDasharray="4 3"
          dot={false}
          isAnimationActive
          animationDuration={600}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
