"use client";

import {
  CandlestickSeries,
  ColorType,
  createChart,
  CrosshairMode,
  HistogramSeries,
  type IChartApi,
  type ISeriesApi,
  LineStyle,
  type UTCTimestamp,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";

import { Skeleton } from "@/components/skeleton";
import { toChartTime } from "@/lib/chart-time";
import { formatNumber, formatPercent, formatPrice } from "@/lib/format";
import { TIMEFRAMES, type TimeframeValue } from "@/lib/instruments";
import { cn } from "@/lib/utils";

interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; candles: Candle[]; source: string | null };

type Loaded = { key: string; state: State };

function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function PriceChart({ symbol, showVolume }: { symbol: string; showVolume: boolean }) {
  const [timeframe, setTimeframe] = useState<TimeframeValue>("1d");
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [hover, setHover] = useState<Candle | null>(null);
  const container = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<{
    candles: ISeriesApi<"Candlestick">;
    volume: ISeriesApi<"Histogram">;
  } | null>(null);
  const intraday = timeframe === "5m" || timeframe === "15m";
  const key = `${symbol}|${timeframe}`;
  // Finché la richiesta corrente non risponde, si mostra lo stato di caricamento.
  const state: State = loaded?.key === key ? loaded.state : { status: "loading" };

  useEffect(() => {
    const controller = new AbortController();
    const limit = TIMEFRAMES.find((t) => t.value === timeframe)?.limit ?? 500;
    fetch(`/api/candles/${symbol}?timeframe=${timeframe}&limit=${limit}`, {
      signal: controller.signal,
    })
      .then(async (r) => {
        if (!r.ok) throw new Error(r.status === 404 ? "Strumento non trovato" : "Dati non disponibili");
        return (await r.json()) as { candles: Candle[]; source: string | null };
      })
      .then((data) =>
        setLoaded({
          key: `${symbol}|${timeframe}`,
          state: { status: "ready", candles: data.candles, source: data.source },
        }),
      )
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setLoaded({
          key: `${symbol}|${timeframe}`,
          state: { status: "error", message: err instanceof Error ? err.message : "Errore" },
        });
      });
    return () => controller.abort();
  }, [symbol, timeframe]);

  useEffect(() => {
    if (!container.current) return;
    const chart = createChart(container.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: token("--mt-surface") },
        textColor: token("--mt-text-muted"),
        fontFamily: getComputedStyle(document.body).fontFamily,
        fontSize: 11,
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: token("--mt-chart-grid") },
        horzLines: { color: token("--mt-chart-grid") },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: token("--mt-chart-crosshair"), style: LineStyle.Dashed, width: 1 },
        horzLine: { color: token("--mt-chart-crosshair"), style: LineStyle.Dashed, width: 1 },
      },
      rightPriceScale: { borderColor: token("--mt-border") },
      timeScale: { borderColor: token("--mt-border"), rightOffset: 4 },
      localization: { locale: "it-IT", priceFormatter: (p: number) => formatPrice(p) },
    });
    const up = token("--mt-up");
    const down = token("--mt-down");
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: up,
      downColor: down,
      wickUpColor: up,
      wickDownColor: down,
      borderVisible: false,
      priceLineColor: token("--mt-text-subtle"),
    });
    const volume = chart.addSeries(HistogramSeries, {
      priceScaleId: "volume",
      priceFormat: { type: "volume" },
      lastValueVisible: false,
      priceLineVisible: false,
    });
    chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    chartRef.current = chart;
    seriesRef.current = { candles, volume };
    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  const candlesData = state.status === "ready" ? state.candles : null;
  const data = useMemo(() => candlesData ?? [], [candlesData]);

  useEffect(() => {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series) return;
    const up = token("--mt-up-muted");
    const down = token("--mt-down-muted");
    series.candles.setData(
      data.map((c) => ({
        time: toChartTime(c.time, intraday) as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    );
    series.volume.setData(
      showVolume
        ? data.map((c) => ({
            time: toChartTime(c.time, intraday) as UTCTimestamp,
            value: c.volume,
            color: c.close >= c.open ? up : down,
          }))
        : [],
    );
    chart.applyOptions({ timeScale: { timeVisible: intraday, secondsVisible: false } });
    chart.timeScale().fitContent();
    if (data.length > 160) {
      chart.timeScale().setVisibleLogicalRange({ from: data.length - 160, to: data.length + 4 });
    }
    const byTime = new Map(data.map((c) => [toChartTime(c.time, intraday), c]));
    const handler = (param: { time?: unknown }) => {
      setHover(typeof param.time === "number" ? (byTime.get(param.time) ?? null) : null);
    };
    chart.subscribeCrosshairMove(handler);
    return () => chart.unsubscribeCrosshairMove(handler);
  }, [data, intraday, showVolume]);

  const shown = hover ?? data.at(-1) ?? null;
  const prev = shown ? data[data.indexOf(shown) - 1] : undefined;
  const change = shown && prev ? (shown.close / prev.close - 1) * 100 : null;

  return (
    <section aria-label="Grafico dei prezzi" className="overflow-hidden rounded-md border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b px-3 py-2">
        <div role="tablist" aria-label="Intervallo" className="flex gap-0.5">
          {TIMEFRAMES.map((t) => (
            <button
              key={t.value}
              role="tab"
              type="button"
              aria-selected={timeframe === t.value}
              onClick={() => setTimeframe(t.value)}
              className={cn(
                "num rounded-sm px-2 py-1 text-xs transition-colors",
                timeframe === t.value
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        <Legend candle={shown} change={change} />
      </div>
      <div className="relative h-[360px] sm:h-[460px]">
        <div ref={container} className="absolute inset-0" />
        {state.status === "loading" && (
          <div className="absolute inset-0 bg-card p-4">
            <Skeleton className="h-full w-full" />
          </div>
        )}
        {state.status === "error" && (
          <Overlay title={state.message} text="Riprova tra poco o cambia intervallo." />
        )}
        {state.status === "ready" && data.length === 0 && (
          <Overlay title="Nessuna candela" text="Per questo intervallo non ci sono ancora dati." />
        )}
      </div>
      <p className="border-t px-3 py-1.5 text-2xs text-subtle">
        {intraday ? "Orari in ora italiana" : "Date di sessione"}
        {state.status === "ready" && state.source ? ` · fonte: ${state.source}` : ""}
      </p>
    </section>
  );
}

function Legend({ candle, change }: { candle: Candle | null; change: number | null }) {
  if (!candle) return null;
  const items: [string, string][] = [
    ["A", formatPrice(candle.open)],
    ["Max", formatPrice(candle.high)],
    ["Min", formatPrice(candle.low)],
    ["C", formatPrice(candle.close)],
  ];
  return (
    <dl className="num flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-2xs">
      {items.map(([k, v]) => (
        <div key={k} className="flex gap-1">
          <dt className="text-subtle">{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
      {change !== null && (
        <dd className={change >= 0 ? "text-up" : "text-down"}>{formatPercent(change)}</dd>
      )}
      {candle.volume > 0 && (
        <div className="hidden gap-1 sm:flex">
          <dt className="text-subtle">Vol</dt>
          <dd>{formatNumber(candle.volume, 0)}</dd>
        </div>
      )}
    </dl>
  );
}

function Overlay({ title, text }: { title: string; text: string }) {
  return (
    <div className="absolute inset-0 grid place-items-center bg-card/90 text-center">
      <div>
        <p className="font-medium">{title}</p>
        <p className="mt-1 text-xs text-muted-foreground">{text}</p>
      </div>
    </div>
  );
}
