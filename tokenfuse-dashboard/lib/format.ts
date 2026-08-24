export function formatCurrency(value: string | number): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(num);
}

export function formatNumber(value: string | number): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  return new Intl.NumberFormat("en-US").format(num);
}

export function formatTokens(value: number): string {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1)}K`;
  }
  return value.toString();
}

export function budgetPercent(used: number, total: number): number {
  if (total === 0) return 0;
  return Math.min(100, (used / total) * 100);
}

export function statusColor(status: string): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "exceeded":
      return "destructive";
    case "warn":
      return "secondary";
    default:
      return "default";
  }
}
