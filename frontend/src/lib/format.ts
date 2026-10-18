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

/** Prezzo con decimali adatti all'ordine di grandezza. */
export function formatPrice(value: number): string {
  const abs = Math.abs(value);
  const decimals = abs >= 1000 ? 2 : abs >= 1 ? 2 : abs >= 0.01 ? 4 : 6;
  return formatNumber(value, decimals);
}

const dateFmt = new Intl.DateTimeFormat("it-IT", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

export function formatDate(iso: string): string {
  return dateFmt.format(new Date(iso));
}
