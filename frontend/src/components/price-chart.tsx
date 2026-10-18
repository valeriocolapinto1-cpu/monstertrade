"use client";

import {
  CandlestickSeries,
  ColorType,
  createChart,
  CrosshairMode,
  HistogramSeries,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  LineSeries,
  LineStyle,
  type SeriesType,
  type UTCTimestamp,
} from "lightweight-charts";
import { Info, SlidersHorizontal } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Skeleton } from "@/components/skeleton";
import { toChartTime } from "@/lib/chart-time";
import { formatNumber, formatPercent, formatPrice } from "@/lib/format";
import { type IndicatorCard, INDICATORS } from "@/lib/indicator-cards";
import { formatIndicator, seriesLabel } from "@/lib/indicator-format";
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

interface IndicatorData {
  time: number[];
  series: Record<string, (number | null)[]>;
  levels: { price: number; touches: number; kind: string }[];
  fibonacci: Record<string, number> | null;
  latest: Record<string, number | null>;
}

interface Loaded {
  key: string;
  status: "ready" | "error";
  candles: Candle[];
  source: string | null;
  indicators: IndicatorData | null;
  message?: string;
}

const LINE_TOKENS = ["--mt-chart-series-1", "--mt-chart-series-3", "--mt-chart-series-2"];
const PANE_HEIGHT = 110;

function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

async function getJson<T>(url: string, signal: AbortSignal): Promise<T> {
  const r = await fetch(url, { signal });
  if (!r.ok) throw new Error(r.status === 404 ? "Nessun dato per questo intervallo" : "Dati non disponibili");
  return (await r.json()) as T;
}

export function PriceChart({ symbol, showVolume }: { symbol: string; showVolume: boolean }) {
  const [timeframe, setTimeframe] = useState<TimeframeValue>("1d");
  const [active, setActive] = useState<string[]>(["sma"]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [hover, setHover] = useState<Candle | null>(null);
  const container = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const baseRef = useRef<{ candles: ISeriesApi<"Candlestick">; volume: ISeriesApi<"Histogram"> } | null>(
    null,
  );
  const extraRef = useRef<{ series: ISeriesApi<SeriesType>[]; lines: IPriceLine[] }>({ series: [], lines: [] });
  const intraday = timeframe === "5m" || timeframe === "15m";
  const key = `${symbol}|${timeframe}`;
  const state = loaded?.key === key ? loaded : null;

  const available = useMemo(
    () => INDICATORS.filter((c) => !c.intradayOnly || intraday),
    [intraday],
  );
  const shownCards = useMemo(
    () => available.filter((c) => active.includes(c.id)),
    [available, active],
  );
  const panes = shownCards.filter((c) => c.placement === "pane");

  useEffect(() => {
    const controller = new AbortController();
    const limit = TIMEFRAMES.find((t) => t.value === timeframe)?.limit ?? 500;
    const q = `timeframe=${timeframe}&limit=${limit}`;
    const k = `${symbol}|${timeframe}`;
    Promise.all([
      getJson<{ candles: Candle[]; source: string | null }>(`/api/candles/${symbol}?${q}`, controller.signal),
      getJson<IndicatorData>(`/api/indicators/${symbol}?${q}`, controller.signal).catch(() => null),
    ])
      .then(([c, i]) =>
        setLoaded({ key: k, status: "ready", candles: c.candles, source: c.source, indicators: i }),
      )
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setLoaded({
          key: k,
          status: "error",
          candles: [],
          source: null,
          indicators: null,
          message: err instanceof Error ? err.message : "Errore",
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
        panes: { separatorColor: token("--mt-border"), enableResize: false },
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
    baseRef.current = { candles, volume };
    return () => {
      chart.remove();
      chartRef.current = null;
      baseRef.current = null;
    };
  }, []);

  const candlesData = state?.status === "ready" ? state.candles : null;
  const data = useMemo(() => candlesData ?? [], [candlesData]);
  const indicatorData = state?.indicators ?? null;

  // Candele e volumi.
  useEffect(() => {
    const chart = chartRef.current;
    const base = baseRef.current;
    if (!chart || !base) return;
    const upMuted = token("--mt-up-muted");
    const downMuted = token("--mt-down-muted");
    base.candles.setData(
      data.map((c) => ({
        time: toChartTime(c.time, intraday) as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    );
    base.volume.setData(
      showVolume
        ? data.map((c) => ({
            time: toChartTime(c.time, intraday) as UTCTimestamp,
            value: c.volume,
            color: c.close >= c.open ? upMuted : downMuted,
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

  // Indicatori: si ricostruiscono serie, riquadri e linee a ogni cambio.
  useEffect(() => {
    const chart = chartRef.current;
    const base = baseRef.current;
    if (!chart || !base) return;
    const extra = extraRef.current;
    for (const line of extra.lines) base.candles.removePriceLine(line);
    for (const s of extra.series) chart.removeSeries(s);
    extra.series = [];
    extra.lines = [];
    for (let i = chart.panes().length - 1; i > 0; i--) chart.removePane(i);
    if (!indicatorData) return;

    const times = indicatorData.time.map((t) => toChartTime(t, intraday) as UTCTimestamp);
    const points = (key: string) =>
      (indicatorData.series[key] ?? []).flatMap((v, i) =>
        v === null ? [] : [{ time: times[i], value: v }],
      );
    const line = (key: string, color: string, pane: number, width: 1 | 2 = 1) => {
      const s = chart.addSeries(
        LineSeries,
        {
          color,
          lineWidth: width,
          priceLineVisible: false,
          lastValueVisible: pane > 0,
          crosshairMarkerVisible: false,
          priceFormat: { type: "custom", formatter: (v: number) => formatIndicator(key, v) },
        },
        pane,
      );
      s.setData(points(key));
      extra.series.push(s as ISeriesApi<SeriesType>);
      return s;
    };
    const muted = token("--mt-text-subtle");

    let paneIndex = 0;
    for (const card of shownCards) {
      if (card.placement === "overlay") {
        card.series.forEach((key, i) =>
          line(
            key,
            card.id === "bollinger"
              ? token("--mt-chart-series-4")
              : token(LINE_TOKENS[i % LINE_TOKENS.length]),
            0,
          ),
        );
        if (card.id === "levels") {
          for (const lv of indicatorData.levels) {
            extra.lines.push(
              base.candles.createPriceLine({
                price: lv.price,
                color: lv.kind === "supporto" ? token("--mt-up") : token("--mt-down"),
                lineStyle: LineStyle.Dotted,
                lineWidth: 1,
                axisLabelVisible: true,
                title: lv.kind === "supporto" ? `S ×${lv.touches}` : `R ×${lv.touches}`,
              }),
            );
          }
        }
        if (card.id === "fibonacci" && indicatorData.fibonacci) {
          for (const [ratio, price] of Object.entries(indicatorData.fibonacci)) {
            extra.lines.push(
              base.candles.createPriceLine({
                price,
                color: token("--mt-chart-series-3"),
                lineStyle: LineStyle.Dashed,
                lineWidth: 1,
                axisLabelVisible: false,
                title: `${ratio.replace(".", ",")}%`,
              }),
            );
          }
        }
        continue;
      }
      if (card.placement !== "pane") continue;
      paneIndex += 1;
      if (card.id === "macd") {
        const hist = chart.addSeries(
          HistogramSeries,
          { priceLineVisible: false, lastValueVisible: false },
          paneIndex,
        );
        const up = token("--mt-up-muted");
        const down = token("--mt-down-muted");
        hist.setData(
          points("macd_hist").map((p) => ({ ...p, color: p.value >= 0 ? up : down })),
        );
        extra.series.push(hist as ISeriesApi<SeriesType>);
        line("macd", token("--mt-chart-series-1"), paneIndex);
        line("macd_signal", token("--mt-chart-series-3"), paneIndex);
      } else {
        card.series.forEach((key, i) =>
          line(key, token(LINE_TOKENS[i % LINE_TOKENS.length]), paneIndex, i === 0 ? 2 : 1),
        );
      }
      const host = extra.series.at(-1);
      for (const g of card.guides ?? []) {
        if (!host) break;
        extra.lines.push(
          host.createPriceLine({ price: g, color: muted, lineStyle: LineStyle.Dotted, lineWidth: 1, axisLabelVisible: false, title: "" }),
        );
      }
    }
    // Proporzioni dei riquadri: il grafico dei prezzi tiene la sua altezza, ogni
    // riquadro aggiunto PANE_HEIGHT pixel (il contenitore cresce di conseguenza).
    const allPanes = chart.panes();
    const total = container.current?.clientHeight ?? 0;
    const mainHeight = Math.max(total - (allPanes.length - 1) * PANE_HEIGHT, PANE_HEIGHT);
    allPanes.forEach((pane, i) => pane.setStretchFactor(i === 0 ? mainHeight : PANE_HEIGHT));
  }, [indicatorData, shownCards, intraday]);

  const shown = hover ?? data.at(-1) ?? null;
  const prev = shown ? data[data.indexOf(shown) - 1] : undefined;
  const change = shown && prev ? (shown.close / prev.close - 1) * 100 : null;
  const loading = state === null;

  const toggle = (id: string) =>
    setActive((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));

  return (
    <div className="space-y-4">
      <section aria-label="Grafico dei prezzi" className="overflow-hidden rounded-md border bg-card">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b px-3 py-2">
          <div className="flex items-center gap-2">
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
            <span aria-hidden className="h-4 w-px bg-border" />
            <button
              type="button"
              aria-expanded={pickerOpen}
              aria-controls="indicator-picker"
              onClick={() => setPickerOpen((o) => !o)}
              className={cn(
                "flex items-center gap-1.5 rounded-sm px-2 py-1 text-xs transition-colors",
                pickerOpen ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <SlidersHorizontal aria-hidden className="size-3.5" />
              Indicatori
              {shownCards.length > 0 && <span className="num text-primary">{shownCards.length}</span>}
            </button>
          </div>
          <Legend candle={shown} change={change} />
        </div>
        {pickerOpen && <Picker cards={available} active={active} onToggle={toggle} />}
        <div
          className="relative"
          style={{ height: `calc(var(--chart-h) + ${panes.length * PANE_HEIGHT}px)` }}
        >
          <div ref={container} className="absolute inset-0" />
          {loading && (
            <div className="absolute inset-0 bg-card p-4">
              <Skeleton className="h-full w-full" />
            </div>
          )}
          {state?.status === "error" && (
            <Overlay title={state.message ?? "Errore"} text="Riprova tra poco o cambia intervallo." />
          )}
          {state?.status === "ready" && data.length === 0 && (
            <Overlay title="Nessuna candela" text="Per questo intervallo non ci sono ancora dati." />
          )}
        </div>
        <p className="border-t px-3 py-1.5 text-2xs text-subtle">
          {intraday ? "Orari in ora italiana" : "Date di sessione"}
          {state?.source ? ` · fonte: ${state.source}` : ""}
          {panes.length > 0 && ` · riquadri: ${panes.map((p) => p.name.split(" ")[0]).join(", ")}`}
        </p>
      </section>
      {shownCards.length > 0 && (
        <section aria-labelledby="schede" className="space-y-2">
          <h2 id="schede" className="text-2xs font-medium uppercase tracking-wider text-muted-foreground">
            Schede degli indicatori attivi
          </h2>
          <div className="grid gap-3 md:grid-cols-2">
            {shownCards.map((card) => (
              <CardView key={card.id} card={card} latest={indicatorData?.latest ?? {}} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function Picker({
  cards,
  active,
  onToggle,
}: {
  cards: IndicatorCard[];
  active: string[];
  onToggle: (id: string) => void;
}) {
  const groups = [...new Set(cards.map((c) => c.group))];
  return (
    <div id="indicator-picker" className="grid gap-x-6 gap-y-3 border-b px-3 py-3 sm:grid-cols-3 lg:grid-cols-6">
      {groups.map((g) => (
        <fieldset key={g} className="space-y-1.5">
          <legend className="mb-1 text-2xs uppercase tracking-wider text-subtle">{g}</legend>
          {cards
            .filter((c) => c.group === g)
            .map((c) => (
              <label key={c.id} className="flex cursor-pointer items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={active.includes(c.id)}
                  onChange={() => onToggle(c.id)}
                  className="size-3.5 accent-[var(--mt-accent)]"
                />
                <span className={active.includes(c.id) ? "text-foreground" : "text-muted-foreground"}>
                  {c.name.split(" (")[0]}
                </span>
              </label>
            ))}
        </fieldset>
      ))}
    </div>
  );
}

function CardView({ card, latest }: { card: IndicatorCard; latest: Record<string, number | null> }) {
  const values = card.series.filter((k) => k in latest);
  return (
    <article className="rounded-md border bg-card">
      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b px-4 py-2.5">
        <h3 className="flex items-center gap-1.5 text-sm font-medium">
          <Info aria-hidden className="size-3.5 text-subtle" />
          {card.name}
        </h3>
        {values.length > 0 && (
          <dl className="num flex flex-wrap gap-x-3 gap-y-0.5 text-xs">
            {values.map((k) => (
              <div key={k} className="flex gap-1 whitespace-nowrap">
                <dt className="text-subtle">{seriesLabel(k)}</dt>
                <dd>{formatIndicator(k, latest[k])}</dd>
              </div>
            ))}
          </dl>
        )}
      </header>
      <dl className="space-y-2 px-4 py-3 text-xs leading-relaxed">
        <div>
          <dt className="text-2xs uppercase tracking-wider text-subtle">Cosa misura</dt>
          <dd className="mt-0.5 text-muted-foreground">{card.measures}</dd>
        </div>
        <div>
          <dt className="text-2xs uppercase tracking-wider text-subtle">Come si legge</dt>
          <dd className="mt-0.5 text-muted-foreground">{card.reading}</dd>
        </div>
        <div>
          <dt className="text-2xs uppercase tracking-wider text-warn">Quando inganna</dt>
          <dd className="mt-0.5 text-muted-foreground">{card.misleads}</dd>
        </div>
      </dl>
    </article>
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
