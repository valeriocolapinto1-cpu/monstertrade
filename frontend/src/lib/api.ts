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
  family: "trend" | "momentum" | "riferimento" | "score";
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

export interface ScoreComparison {
  horizon: "day" | "swing" | "long";
  instruments: number;
  score_sharpe: number;
  simple_sharpe: number;
  best_simple_sharpe: number;
  beats_best: number;
  beats_average: number;
  score_return: number;
  simple_return: number;
  improves: boolean;
}

export interface BacktestReport {
  generated_at: string;
  criterion_met: boolean;
  positive_strategies: number;
  tested_strategies: number;
  score_improves?: boolean;
  score_comparison?: ScoreComparison[];
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

export type Horizon = "day" | "swing" | "long";
export type RiskLabel = "Basso" | "Medio" | "Alto" | "Molto alto";

export interface SignalEntry {
  key: string;
  component: string;
  label: string;
  value: number;
}

export interface Signal {
  symbol: string;
  horizon: Horizon;
  ts: string;
  score: number;
  components: Record<string, number | null>;
  favorable: SignalEntry[];
  contrary: SignalEntry[];
  risk_label: RiskLabel;
  weights: Record<string, number>;
}

export interface SentimentItem {
  date: string;
  source: string;
  score: number;
  mentions: number;
}

export interface SentimentData {
  symbol: string;
  underlying: string;
  items: SentimentItem[];
}

export function getSignals(symbol?: string): Promise<Signal[]> {
  return apiGet<Signal[]>(symbol ? `/api/instruments/${symbol}/signals` : "/api/signals");
}

export function getSentiment(symbol: string, days = 14): Promise<SentimentData> {
  return apiGet<SentimentData>(`/api/instruments/${symbol}/sentiment?days=${days}`);
}
