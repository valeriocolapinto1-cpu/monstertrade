const LOCALE = "it-IT";

const eur = new Intl.NumberFormat(LOCALE, {
  style: "currency",
  currency: "EUR",
  useGrouping: "always",
});

export function formatEur(value: number): string {
  return eur.format(value);
}

export function formatNumber(value: number, decimals = 2): string {
  return new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
    useGrouping: "always",
  }).format(value);
}

/** Variazione percentuale con segno esplicito, es. "+1,25%". */
export function formatPercent(value: number, decimals = 2): string {
  return new Intl.NumberFormat(LOCALE, {
    style: "percent",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
    signDisplay: "exceptZero",
  }).format(value / 100);
}

export type Trend = "up" | "down" | "flat";

export function trendOf(value: number): Trend {
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "flat";
}
