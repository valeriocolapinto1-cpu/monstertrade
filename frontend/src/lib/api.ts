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

export interface IndicatorSnapshot {
  time: number[];
  metrics: Record<string, number | null>;
  latest: Record<string, number | null>;
}

export interface BacktestRow {
  symbol: string;
  horizon: "day" | "swing" | "long";
  strategy: string;
  strategy_name: string;
  family: "trend" | "momentum" | "riferimento";
  start: string;
  end: string;
  bars: number;
  total_return: number | null;
  cagr: number | null;
  sharpe: number | null;
  max_drawdown: number | null;
  trades: number;
  win_rate: number | null;
  exposure: number | null;
  costs_paid: number | null;
  first_half: number | null;
  second_half: number | null;
}

export interface BacktestReport {
  generated_at: string;
  criterion_met: boolean;
  positive_strategies: number;
  tested_strategies: number;
  results: BacktestRow[];
}

export interface Correlations {
  window: number;
  symbols: string[];
  matrix: (number | null)[][];
}

export function getIndicatorSnapshot(symbol: string, limit = 252): Promise<IndicatorSnapshot> {
  return apiGet<IndicatorSnapshot>(`/api/instruments/${symbol}/indicators?timeframe=1d&limit=${limit}`);
}

export function getBacktest(symbol?: string): Promise<BacktestReport> {
  return apiGet<BacktestReport>(symbol ? `/api/backtest?symbol=${symbol}` : "/api/backtest");
}

export function getCorrelations(): Promise<Correlations> {
  return apiGet<Correlations>("/api/correlations");
}
