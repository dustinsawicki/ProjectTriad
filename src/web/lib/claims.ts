export type ClaimRow = {
  ClaimId: string;
  ClaimNumber: string;
  LossType: string;
  Status: string;
  ReportedAmount: number | null;
  ReserveAmount: number | null;
  SettledAmount: number | null;
  AssignedAdjuster: string | null;
  CreatedUtc: string;
  top_fraud_score: number | null;
  route: string | null;
};

export const STATUS_ORDER = ["open", "triaged", "assessed", "settled", "denied"] as const;
export const ROUTE_ORDER = ["stp", "desk", "field", "siu"] as const;

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0
});

const wholeCurrencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
  notation: "compact"
});

const percentFormatter = new Intl.NumberFormat("en-US", {
  style: "percent",
  maximumFractionDigits: 1
});

function startCase(value: string) {
  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
    .join(" ");
}

export function formatCurrency(value: number | null | undefined) {
  return value == null ? "—" : currencyFormatter.format(value);
}

export function formatCompactCurrency(value: number | null | undefined) {
  return value == null ? "—" : wholeCurrencyFormatter.format(value);
}

export function formatPercent(value: number | null | undefined) {
  return value == null ? "—" : percentFormatter.format(value);
}

export function formatLossType(value: string | null | undefined) {
  return value ? startCase(value) : "Unclassified";
}

export function formatStatus(value: string | null | undefined) {
  return value ? startCase(value) : "Unknown";
}

export function formatRoute(value: string | null | undefined) {
  return value ? startCase(value) : "Unassigned";
}
