export type Kind = "index" | "leveraged_etf" | "crypto" | "crypto_etp";

export const KIND_LABEL: Record<Kind, string> = {
  index: "Indici",
  leveraged_etf: "ETF a leva",
  crypto: "Crypto",
  crypto_etp: "ETP crypto",
};

export const KIND_ORDER: Kind[] = ["index", "leveraged_etf", "crypto", "crypto_etp"];

export function leverageLabel(leverage: number): string | null {
  if (leverage === 1) return null;
  return `${leverage > 0 ? "" : "−"}${Math.abs(leverage)}x`;
}

export const TIMEFRAMES = [
  { value: "5m", label: "5m", limit: 600 },
  { value: "15m", label: "15m", limit: 600 },
  { value: "1d", label: "1G", limit: 1500 },
  { value: "1w", label: "1S", limit: 700 },
] as const;

export type TimeframeValue = (typeof TIMEFRAMES)[number]["value"];

export function isTimeframe(value: string): value is TimeframeValue {
  return TIMEFRAMES.some((t) => t.value === value);
}
