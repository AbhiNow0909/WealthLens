"use client";

import Link from "next/link";
import type { Holding, NavPoint } from "@/lib/api";
import { formatCompactCurrency, formatPercent, formatUnits, formatNav } from "@/lib/formatters";
import Sparkline from "@/components/charts/Sparkline";

interface Props {
  holding: Holding;
  navHistory: NavPoint[];
}

export default function FundCard({ holding, navHistory }: Props) {
  const gain = (holding.current_value ?? 0) - (holding.invested_value ?? 0);
  const gainPct = holding.invested_value > 0 ? (gain / holding.invested_value) * 100 : 0;
  const positive = gain >= 0;

  return (
    <Link
      href={`/fund/${holding.isin}`}
      className="block bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5 hover:border-[var(--accent)] transition-colors"
    >
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="min-w-0">
          <p className="text-sm font-medium text-[var(--text-primary)] leading-tight line-clamp-2">
            {holding.scheme_name}
          </p>
          <p className="text-xs text-[var(--text-secondary)] mt-1">{holding.isin}</p>
        </div>
        <span
          className={`text-xs tabular-nums shrink-0 ${
            positive ? "text-[var(--gain)]" : "text-[var(--loss)]"
          }`}
        >
          {formatPercent(gainPct)}
        </span>
      </div>

      <div className="flex items-end justify-between mb-3">
        <div>
          <p className="text-lg font-semibold tabular-nums text-[var(--text-primary)]">
            {formatCompactCurrency(holding.current_value)}
          </p>
          <p className="text-xs text-[var(--text-secondary)] tabular-nums mt-0.5">
            {formatUnits(holding.units_held)} units · {formatNav(holding.current_nav)}
          </p>
        </div>
      </div>

      <Sparkline data={navHistory} />
    </Link>
  );
}
