"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getHoldings, getPortfolioSummary, syncNavs, type Holding, type PortfolioSummary } from "@/lib/api";
import { formatCompactCurrency, formatPercent } from "@/lib/formatters";
import CASUploadDropzone from "@/components/portfolio/CASUploadDropzone";
import { createClient } from "@/lib/supabase-browser";
import Link from "next/link";

interface Props {
  userId: string;
}

export default function DashboardClient({ userId: _ }: Props) {
  const router = useRouter();
  const [holdings, setHoldings] = useState<Holding[] | null>(null);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);

  async function handleSync() {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const result = await syncNavs();
      const funds = result.funds_synced as number;
      const rows = result.nav_rows_upserted as number;
      setSyncMsg(`Updated ${funds} fund${funds !== 1 ? "s" : ""} · ${rows} NAV rows`);
      await load();
    } catch {
      setSyncMsg("Sync failed — check backend logs");
    } finally {
      setSyncing(false);
    }
  }

  async function handleLogout() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
  }

  async function load() {
    try {
      const [h, s] = await Promise.all([getHoldings(), getPortfolioSummary()]);
      setHoldings(h);
      setSummary(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load portfolio");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  if (loading) return <DashboardSkeleton />;
  if (error) return (
    <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center">
      <p className="text-[var(--loss)] text-sm">{error}</p>
    </div>
  );

  const hasHoldings = holdings && holdings.length > 0;

  return (
    <div className="min-h-screen bg-[var(--bg)]">
      {/* Nav */}
      <nav className="border-b border-[var(--border)] px-6 py-4 flex items-center justify-between">
        <span className="text-[var(--text-primary)] font-semibold tracking-tight">WealthLens</span>
        <div className="flex items-center gap-6 text-sm text-[var(--text-secondary)]">
          <Link href="/dashboard" className="text-[var(--text-primary)]">Portfolio</Link>
          <Link href="/compare" className="hover:text-[var(--text-primary)] transition-colors">Compare</Link>
          <Link href="/assistant" className="hover:text-[var(--text-primary)] transition-colors">Assistant</Link>
          <button
            onClick={handleSync}
            disabled={syncing}
            className="hover:text-[var(--text-primary)] transition-colors disabled:opacity-40"
          >
            {syncing ? "Syncing…" : "Refresh prices"}
          </button>
          <button
            onClick={handleLogout}
            className="hover:text-[var(--text-primary)] transition-colors"
          >
            Sign out
          </button>
        </div>
      </nav>

      {syncMsg && (
        <div className="border-b border-[var(--border)] px-6 py-2 text-xs text-center text-[var(--text-secondary)]">
          {syncMsg}
        </div>
      )}

      <div className="max-w-7xl mx-auto px-6 py-8">
        {!hasHoldings ? (
          /* Empty state */
          <div className="flex flex-col items-center justify-center py-24">
            <h1 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
              Welcome to WealthLens
            </h1>
            <p className="text-[var(--text-secondary)] text-sm mb-10 text-center max-w-sm">
              Upload your NSDL CAS statement to import your mutual fund portfolio and start tracking.
            </p>
            <CASUploadDropzone onSuccess={load} />
          </div>
        ) : (
          /* Portfolio view */
          <>
            {/* Summary cards */}
            {summary && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                <SummaryCard label="Current Value" value={formatCompactCurrency(summary.total_value)} />
                <SummaryCard label="Invested" value={formatCompactCurrency(summary.total_invested)} />
                <SummaryCard
                  label="Total Gain"
                  value={formatCompactCurrency(summary.total_gain)}
                  valueClass={summary.total_gain >= 0 ? "text-[var(--gain)]" : "text-[var(--loss)]"}
                />
                <SummaryCard
                  label="Return"
                  value={formatPercent(summary.total_gain_pct)}
                  valueClass={summary.total_gain_pct >= 0 ? "text-[var(--gain)]" : "text-[var(--loss)]"}
                />
              </div>
            )}

            {/* Holdings table */}
            <div className="bg-[var(--surface)] rounded-xl border border-[var(--border)] overflow-hidden">
              <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
                <h2 className="text-sm font-medium text-[var(--text-primary)]">
                  Holdings ({holdings.length})
                </h2>
                <button
                  onClick={() => setShowUpload((v) => !v)}
                  className="text-xs text-[var(--accent)] hover:opacity-80 transition-opacity"
                >
                  {showUpload ? "Cancel" : "Update statement"}
                </button>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[var(--text-secondary)] text-xs">
                    <th className="text-left px-5 py-3 font-medium">Fund</th>
                    <th className="text-right px-5 py-3 font-medium">Units</th>
                    <th className="text-right px-5 py-3 font-medium">NAV</th>
                    <th className="text-right px-5 py-3 font-medium">Current Value</th>
                    <th className="text-right px-5 py-3 font-medium">Invested</th>
                    <th className="text-right px-5 py-3 font-medium">Gain</th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.map((h) => {
                    const gain = (h.current_value ?? 0) - (h.invested_value ?? 0);
                    const gainPct = h.invested_value > 0 ? (gain / h.invested_value) * 100 : 0;
                    return (
                      <tr
                        key={h.id}
                        className="border-t border-[var(--border)] hover:bg-white/5 transition-colors cursor-pointer"
                        onClick={() => window.location.href = `/fund/${h.isin}`}
                      >
                        <td className="px-5 py-4">
                          <p className="text-[var(--text-primary)] font-medium leading-tight">{h.scheme_name}</p>
                          <p className="text-[var(--text-secondary)] text-xs mt-0.5">{h.isin}</p>
                        </td>
                        <td className="px-5 py-4 text-right tabular-nums text-[var(--text-primary)]">
                          {h.units_held?.toFixed(3)}
                        </td>
                        <td className="px-5 py-4 text-right tabular-nums text-[var(--text-primary)]">
                          ₹{h.current_nav?.toFixed(2)}
                        </td>
                        <td className="px-5 py-4 text-right tabular-nums text-[var(--text-primary)]">
                          {formatCompactCurrency(h.current_value)}
                        </td>
                        <td className="px-5 py-4 text-right tabular-nums text-[var(--text-secondary)]">
                          {formatCompactCurrency(h.invested_value)}
                        </td>
                        <td className={`px-5 py-4 text-right tabular-nums ${gain >= 0 ? "text-[var(--gain)]" : "text-[var(--loss)]"}`}>
                          {formatPercent(gainPct)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Inline CAS re-upload — only visible when toggled */}
            {showUpload && (
              <div className="mt-6">
                <CASUploadDropzone
                  onSuccess={() => {
                    setShowUpload(false);
                    load();
                  }}
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function SummaryCard({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl px-5 py-4">
      <p className="text-[var(--text-secondary)] text-xs mb-1">{label}</p>
      <p className={`tabular-nums text-lg font-semibold ${valueClass ?? "text-[var(--text-primary)]"}`}>{value}</p>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="min-h-screen bg-[var(--bg)] p-6">
      <div className="max-w-7xl mx-auto">
        <div className="grid grid-cols-4 gap-4 mb-8">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-[var(--surface)] border border-[var(--border)] rounded-xl h-20 animate-pulse" />
          ))}
        </div>
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl h-64 animate-pulse" />
      </div>
    </div>
  );
}
