"use client";

import { useState } from "react";
import Link from "next/link";
import type { TrailingReturnsRow } from "@/lib/api";

const PERIODS = ["1w", "1m", "3m", "6m", "1y", "3y", "5y"] as const;
type PeriodKey = (typeof PERIODS)[number];
type SortKey = "name" | PeriodKey;

function cellColor(v: number | null): string {
  if (v === null || v === undefined) return "text-[var(--text-secondary)] opacity-40";
  return v >= 0 ? "text-[var(--gain)]" : "text-[var(--loss)]";
}

function fmt(v: number | null): string {
  if (v === null || v === undefined) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

interface Props {
  data: TrailingReturnsRow[];
  highlightIsin?: string;
}

export default function TrailingReturnsTable({ data, highlightIsin }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("1y");
  const [asc, setAsc] = useState(false);

  if (!data || data.length === 0) {
    return (
      <p className="text-sm text-[var(--text-secondary)] py-8 text-center">
        No trailing-returns data yet. Refresh prices to populate NAV history.
      </p>
    );
  }

  const sorted = [...data].sort((a, b) => {
    if (sortKey === "name") {
      return asc ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name);
    }
    // nulls sort last regardless of direction
    const av = a[sortKey];
    const bv = b[sortKey];
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    return asc ? av - bv : bv - av;
  });

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setAsc((v) => !v);
    } else {
      setSortKey(key);
      setAsc(false);
    }
  }

  const arrow = (key: SortKey) => (sortKey === key ? (asc ? " ↑" : " ↓") : "");

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-[var(--text-secondary)] text-xs border-b border-[var(--border)]">
            <th
              className="text-left px-4 py-3 font-medium cursor-pointer select-none hover:text-[var(--text-primary)]"
              onClick={() => toggleSort("name")}
            >
              Fund{arrow("name")}
            </th>
            {PERIODS.map((p) => (
              <th
                key={p}
                className="text-right px-4 py-3 font-medium cursor-pointer select-none hover:text-[var(--text-primary)] uppercase"
                onClick={() => toggleSort(p)}
              >
                {p}
                {arrow(p)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const highlighted = row.isin === highlightIsin;
            return (
              <tr
                key={row.isin}
                className={`border-b border-[var(--border)] transition-colors ${
                  highlighted ? "bg-[var(--accent)]/10" : "hover:bg-white/5"
                }`}
              >
                <td className="px-4 py-3 max-w-[260px]">
                  <Link
                    href={`/fund/${row.isin}`}
                    className="text-[var(--text-primary)] hover:text-[var(--accent)] transition-colors line-clamp-1"
                  >
                    {row.name}
                  </Link>
                </td>
                {PERIODS.map((p) => (
                  <td
                    key={p}
                    className={`px-4 py-3 text-right tabular-nums ${cellColor(row[p])}`}
                  >
                    {fmt(row[p])}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
