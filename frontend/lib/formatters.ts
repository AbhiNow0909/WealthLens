// Indian number format: ₹12,34,567.89
export function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

// Always show sign: +12.34% or -5.67%
export function formatPercent(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

// Compact large numbers: ₹12.3L, ₹2.5Cr
export function formatCompactCurrency(value: number): string {
  if (Math.abs(value) >= 1_00_00_000) {
    return `₹${(value / 1_00_00_000).toFixed(2)}Cr`;
  }
  if (Math.abs(value) >= 1_00_000) {
    return `₹${(value / 1_00_000).toFixed(2)}L`;
  }
  return formatCurrency(value);
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function formatNumber(value: number, decimals = 2): string {
  return value.toFixed(decimals);
}

// Unit balance: 3 decimals, grouped (e.g. 63,479.738)
export function formatUnits(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: 3,
    maximumFractionDigits: 3,
  }).format(value);
}

// NAV: full ₹ with 2 decimals (e.g. ₹874.67)
export function formatNav(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `₹${value.toFixed(2)}`;
}
