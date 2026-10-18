import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { authConfig, SESSION_COOKIE, verifySessionToken } from "@/lib/session";

/** Seconda verifica della sessione, oltre al proxy, prima di ogni lettura di dati. */
export async function requireSession(): Promise<void> {
  // Leggere i cookie rende la pagina dinamica: niente dati nel prerender della build.
  const jar = await cookies();
  const { enabled, secret, misconfigured } = authConfig();
  if (misconfigured) throw new Error("Accesso non configurato");
  if (!enabled) return;
  const token = jar.get(SESSION_COOKIE)?.value;
  if (!(await verifySessionToken(token, secret, Math.floor(Date.now() / 1000)))) {
    redirect("/accesso");
  }
}

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

/** Intestazioni per il backend: il segreto condiviso resta solo lato server. */
export function apiHeaders(): Record<string, string> {
  const secret = process.env.API_SHARED_SECRET;
  return secret ? { "X-API-Key": secret } : {};
}

export async function apiGet<T>(path: string): Promise<T> {
  await requireSession();
  const response = await fetch(`${apiBase()}${path}`, {
    cache: "no-store",
    headers: apiHeaders(),
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

export interface Idea {
  id: number;
  symbol: string;
  name: string;
  leverage: number;
  horizon: Horizon;
  created_at: string;
  score: number;
  entry: number;
  stop: number;
  target: number;
  size_eur: number;
  risk_eur: number;
  costs_eur: number;
  risk_label: RiskLabel;
  motivation: string;
  warnings: string[];
  status: "proposta" | "aperta" | "chiusa" | "scaduta" | "annullata";
  expires_at: string;
}

export interface Today {
  generated_at: string;
  risk_source: "simulazione" | "conto";
  capital: number;
  equity: number;
  day_pnl: number;
  daily_limit_reached: boolean;
  open_positions: number;
  limits: {
    risk_per_trade: number;
    max_daily_loss: number;
    max_open_positions: number;
    max_lev3_exposure: number;
  };
  proposals: Idea[];
  skipped: { symbol: string; name: string; horizon: Horizon; score: number; reason: string }[];
}

export interface Position {
  symbol: string;
  name: string;
  leverage: number;
  horizon: Horizon;
  entry_ts: string;
  entry_price: number;
  last_price: number;
  stop: number;
  target: number;
  size_eur: number;
  value: number;
  pnl: number;
  pnl_pct: number;
}

export interface Portfolio {
  capital: number;
  equity: number;
  invested: number;
  cash: number;
  day_pnl: number;
  day_pnl_limit: number;
  lev3_exposure: number;
  lev3_limit: number;
  positions: Position[];
  correlations: Record<string, Record<string, number>>;
}

export interface JournalItem extends Idea {
  entry_ts: string | null;
  entry_price: number | null;
  exit_ts: string | null;
  exit_price: number | null;
  exit_reason: "stop" | "obiettivo" | "tempo" | "segnale" | null;
  pnl_eur: number | null;
  fees_eur: number | null;
  mode: "simulato" | "reale" | null;
}

export interface Journal {
  stats: {
    trades: number;
    win_rate: number | null;
    avg_pnl: number | null;
    avg_pnl_pct: number | null;
    total_pnl: number;
    max_drawdown: number | null;
    fees: number;
  };
  items: JournalItem[];
}

export const getToday = () => apiGet<Today>("/api/today");
export const getPortfolio = () => apiGet<Portfolio>("/api/portfolio");
export const getJournal = () => apiGet<Journal>("/api/journal");

export interface BrokerPosition {
  ticker: string;
  symbol: string | null;
  name: string | null;
  leverage: number | null;
  quantity: number;
  average_price: number;
  current_price: number;
  value: number;
  pnl: number;
}

export interface BrokerPortfolio {
  configured: boolean;
  env?: "live" | "demo";
  read_only?: boolean;
  summary?: { currency: string; total: number; cash: number; invested: number; unrealized_pnl: number };
  risk?: {
    day_pnl: number;
    day_pnl_limit: number;
    daily_limit_reached: boolean;
    positions: number;
    max_positions: number;
    lev3_exposure: number;
    lev3_limit: number;
    risk_per_trade: number;
  };
  positions?: BrokerPosition[];
}

export const getBrokerPortfolio = () => apiGet<BrokerPortfolio>("/api/broker/portfolio");
