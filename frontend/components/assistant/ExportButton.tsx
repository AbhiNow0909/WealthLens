"use client";

import { useState } from "react";
import { exportReport, type ExportFormat } from "@/lib/api";

const LABELS: Record<ExportFormat, string> = {
  excel: "Excel",
  word: "Word",
  ppt: "PowerPoint",
};

export default function ExportButton({ format }: { format: ExportFormat }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  async function handleClick() {
    setLoading(true);
    setError(false);
    try {
      const result = await exportReport(format);
      if (result.export_url) {
        // Signed URL — open to download the generated file
        window.open(result.export_url, "_blank");
      } else {
        setError(true);
      }
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      className="px-4 py-2 rounded-lg border border-[var(--border)] text-sm text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--text-primary)] transition-colors disabled:opacity-40"
    >
      {loading ? "Generating…" : error ? `${LABELS[format]} — retry` : LABELS[format]}
    </button>
  );
}
