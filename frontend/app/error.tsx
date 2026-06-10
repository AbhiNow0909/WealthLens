"use client";

import { useEffect } from "react";
import Link from "next/link";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="min-h-screen bg-[var(--bg)] flex flex-col items-center justify-center gap-4 px-6 text-center">
      <h1 className="text-lg font-semibold text-[var(--text-primary)]">Something went wrong</h1>
      <p className="text-sm text-[var(--text-secondary)] max-w-sm">
        An unexpected error occurred. You can try again, or head back to your portfolio.
      </p>
      <div className="flex gap-3 mt-2">
        <button
          onClick={reset}
          className="px-4 py-2 rounded-lg bg-[var(--accent)] text-white text-sm font-medium"
        >
          Try again
        </button>
        <Link
          href="/dashboard"
          className="px-4 py-2 rounded-lg border border-[var(--border)] text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          Back to portfolio
        </Link>
      </div>
    </div>
  );
}
