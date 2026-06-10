import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-[var(--bg)] flex flex-col items-center justify-center gap-4 px-6 text-center">
      <h1 className="text-3xl font-semibold text-[var(--text-primary)]">404</h1>
      <p className="text-sm text-[var(--text-secondary)]">This page doesn&apos;t exist.</p>
      <Link
        href="/dashboard"
        className="px-4 py-2 rounded-lg bg-[var(--accent)] text-white text-sm font-medium"
      >
        Back to portfolio
      </Link>
    </div>
  );
}
