import "server-only";

export type InstrumentKind = "index" | "leveraged_etf" | "crypto" | "crypto_etp";

export interface Instrument {
  symbol: string;
  name: string;
  kind: InstrumentKind;
  currency: string;
  leverage: number;
  underlying: string | null;
  reference_ticker: string | null;
  synthetic: boolean;
  last_price: number | null;
  change_pct: number | null;
  last_ts: string | null;
}

export interface QualityItem {
  symbol: string;
  timeframe: string;
  rows: number;
  first: string | null;
  last: string | null;
  missing: number;
  invalid: number;
  outliers: string[];
  complete: boolean;
}

export interface Quality {
  generated_at: string;
  complete: boolean;
  items: QualityItem[];
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

/** URL del backend: solo lato server, mai esposto al browser. */
export function apiBase(): string {
  return process.env.API_URL ?? "http://localhost:8000";
}

export const SYMBOL_PATTERN = /^[A-Z0-9]{2,16}$/;

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(15_000),
  });
  if (!response.ok) {
    throw new ApiError(`Richiesta non riuscita (${response.status})`, response.status);
  }
  return (await response.json()) as T;
}

export function getInstruments(): Promise<Instrument[]> {
  return apiGet<Instrument[]>("/api/instruments");
}

export function getQuality(): Promise<Quality> {
  return apiGet<Quality>("/api/quality");
}
