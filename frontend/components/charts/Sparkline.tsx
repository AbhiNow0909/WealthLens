"use client";

import { LineChart, Line, YAxis, ResponsiveContainer } from "recharts";
import type { NavPoint } from "@/lib/api";

// Palette hex values (SVG stroke is most reliable with literal colors)
const GAIN = "#22C55E";
const LOSS = "#EF4444";

interface Props {
  data: NavPoint[];
  height?: number;
}

/**
 * Signature element: a subtle 12-month NAV curve — no axes, no labels, no grid.
 * Colour reflects net direction over the window. The one motion element in the UI.
 */
export default function Sparkline({ data, height = 48 }: Props) {
  if (!data || data.length < 2) {
    return (
      <div
        style={{ height }}
        className="flex items-center justify-center text-[10px] text-[var(--text-secondary)]"
      >
        no price history
      </div>
    );
  }

  const first = data[0].nav;
  const last = data[data.length - 1].nav;
  const color = last >= first ? GAIN : LOSS;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 4, right: 0, bottom: 4, left: 0 }}>
        {/* Domain set to data range so small movements remain visible */}
        <YAxis domain={["dataMin", "dataMax"]} hide />
        <Line
          type="monotone"
          dataKey="nav"
          stroke={color}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive
          animationDuration={800}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
