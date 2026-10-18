import { formatNumber, formatPrice } from "@/lib/format";

/** Valore leggibile dell'ultimo dato di un indicatore. */
export function formatIndicator(key: string, value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  if (key.startsWith("rsi") || key.startsWith("stoch") || key === "adx" || key.endsWith("_di")) {
    return formatNumber(value, 1);
  }
  if (key === "atr_pct") return `${formatNumber(value, 2)}%`;
  if (key === "obv") return formatNumber(value, 0);
  if (key.startsWith("macd")) return formatNumber(value, Math.abs(value) < 1 ? 4 : 2);
  return formatPrice(value);
}

const LABELS: Record<string, string> = {
  macd: "MACD",
  macd_signal: "Segnale",
  macd_hist: "Istogramma",
  adx: "ADX",
  plus_di: "+DI",
  minus_di: "−DI",
  rsi_14: "RSI",
  stoch_k: "%K",
  stoch_d: "%D",
  bb_upper: "Superiore",
  bb_mid: "Media",
  bb_lower: "Inferiore",
  atr_pct: "ATR",
  obv: "OBV",
  vwap: "VWAP",
};

/** Etichetta breve di una serie, es. "sma_200" → "SMA 200". */
export function seriesLabel(key: string): string {
  if (LABELS[key]) return LABELS[key];
  const [name, n] = key.split("_");
  return n ? `${name.toUpperCase()} ${n}` : key;
}
