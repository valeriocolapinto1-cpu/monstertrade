import { ChevronLeft } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Badge } from "@/components/badge";
import { Change } from "@/components/change";
import { BacktestTable } from "@/components/backtest-table";
import { PriceChart } from "@/components/price-chart";
import { RiskPanel } from "@/components/risk-panel";
import {
  type Correlations,
  getBacktest,
  getCorrelations,
  getIndicatorSnapshot,
  getInstruments,
  getQuality,
  type Instrument,
  type QualityItem,
  SYMBOL_PATTERN,
} from "@/lib/api";
import { formatDate, formatNumber, formatPrice } from "@/lib/format";
import { RISK_CARDS } from "@/lib/indicator-cards";
import { KIND_LABEL, leverageLabel } from "@/lib/instruments";

export async function generateMetadata({
  params,
}: PageProps<"/strumenti/[symbol]">): Promise<Metadata> {
  const { symbol } = await params;
  return { title: symbol };
}

export default async function StrumentoPage({ params }: PageProps<"/strumenti/[symbol]">) {
  const { symbol } = await params;
  if (!SYMBOL_PATTERN.test(symbol)) notFound();
  const [instruments, quality, snapshot, backtest, correlations] = await Promise.all([
    getInstruments(),
    getQuality().catch(() => null),
    getIndicatorSnapshot(symbol).catch(() => null),
    getBacktest(symbol).catch(() => null),
    getCorrelations().catch(() => null),
  ]);
  const item = instruments.find((i) => i.symbol === symbol);
  if (!item) notFound();
  const checks = quality?.items.filter((q) => q.symbol === symbol) ?? [];

  return (
    <div className="space-y-4">
      <Link
        href="/strumenti"
        className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
      >
        <ChevronLeft aria-hidden className="size-3.5" />
        Strumenti
      </Link>
      <Header item={item} />
      <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
        <PriceChart symbol={item.symbol} showVolume={!item.synthetic && item.kind === "crypto"} />
        <aside className="space-y-4">
          <Details item={item} />
          {snapshot && (
            <RiskPanel metrics={snapshot.metrics} latest={snapshot.latest} leverage={item.leverage} />
          )}
          {correlations && <TopCorrelations symbol={item.symbol} data={correlations} />}
          <DataQuality checks={checks} />
        </aside>
      </div>
      <section aria-labelledby="backtest" className="rounded-md border bg-card">
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-b px-4 py-2">
          <h2 id="backtest" className="text-2xs font-medium uppercase tracking-wider text-muted-foreground">
            Backtest delle strategie semplici
          </h2>
          <Link href="/strumenti/backtest" className="text-xs text-primary hover:underline">
            Tutti gli strumenti
          </Link>
        </div>
        {backtest ? (
          <BacktestTable rows={backtest.results} />
        ) : (
          <p className="px-4 py-3 text-xs text-muted-foreground">Backtest non disponibile.</p>
        )}
        <p className="border-t px-4 py-2 text-2xs leading-relaxed text-subtle">
          Segnale alla chiusura, esecuzione all&apos;apertura successiva, solo posizioni lunghe. Costi per lato
          inclusi (spread stimato e cambio valuta 0,15% sugli strumenti non in euro). Risultati passati, non
          una previsione.
        </p>
      </section>
    </div>
  );
}

function TopCorrelations({ symbol, data }: { symbol: string; data: Correlations }) {
  const i = data.symbols.indexOf(symbol);
  if (i < 0) return null;
  const rows = data.symbols
    .map((s, j) => ({ s, v: data.matrix[i][j] }))
    .filter((r) => r.s !== symbol && r.v !== null)
    .sort((a, b) => Math.abs(b.v ?? 0) - Math.abs(a.v ?? 0))
    .slice(0, 5);
  return (
    <section aria-labelledby="correlazioni" className="rounded-md border bg-card">
      <h2
        id="correlazioni"
        className="border-b px-4 py-2 text-2xs font-medium uppercase tracking-wider text-muted-foreground"
        title={RISK_CARDS.correlation.measures}
      >
        Più correlati · {data.window} giorni
      </h2>
      <ul className="divide-y text-sm">
        {rows.map(({ s, v }) => (
          <li key={s} className="flex items-center justify-between gap-3 px-4 py-2">
            <Link href={`/strumenti/${s}`} className="num hover:text-primary">
              {s}
            </Link>
            <span className="flex items-center gap-2">
              <span aria-hidden className="h-1 w-16 overflow-hidden rounded-full bg-surface-hover">
                <span
                  className={`block h-full ${(v ?? 0) >= 0 ? "bg-primary" : "bg-down"}`}
                  style={{ width: `${Math.abs(v ?? 0) * 100}%` }}
                />
              </span>
              <span className="num w-12 text-right text-xs">{formatNumber(v ?? 0, 2)}</span>
            </span>
          </li>
        ))}
      </ul>
      <p className="border-t px-4 py-2 text-2xs text-subtle">Sopra 0,80 due posizioni non diversificano.</p>
    </section>
  );
}

function Header({ item }: { item: Instrument }) {
  const lev = leverageLabel(item.leverage);
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
      <div>
        <div className="flex items-center gap-2 text-2xs text-subtle">
          <span className="num">{item.symbol}</span>
          <span>·</span>
          <span>{KIND_LABEL[item.kind]}</span>
          {lev && <Badge tone={item.leverage < 0 ? "down" : "neutral"}>{lev}</Badge>}
        </div>
        <h1 className="mt-0.5 text-2xl font-semibold tracking-tight">{item.name}</h1>
      </div>
      <div className="sm:text-right">
        <p className="num text-3xl font-medium leading-none tracking-tight">
          {item.last_price === null ? "—" : formatPrice(item.last_price)}
          <span className="ml-1.5 text-sm text-subtle">{item.synthetic ? "pt" : item.currency}</span>
        </p>
        <p className="mt-1 text-xs">
          <Change value={item.change_pct} />
          {item.last_ts && (
            <span className="ml-2 text-muted-foreground">chiusura {formatDate(item.last_ts)}</span>
          )}
        </p>
      </div>
    </div>
  );
}

function Details({ item }: { item: Instrument }) {
  const rows: [string, React.ReactNode][] = [
    ["Tipo", KIND_LABEL[item.kind]],
    ["Leva", leverageLabel(item.leverage) ?? "Nessuna"],
    ["Sottostante", item.underlying ?? "—"],
    ["Valuta", item.synthetic ? "Punti (base 100)" : item.currency],
    ["Ticker di riferimento", item.reference_ticker ?? "—"],
  ];
  return (
    <section aria-labelledby="dettagli" className="rounded-md border bg-card">
      <h2 id="dettagli" className="border-b px-4 py-2 text-2xs font-medium uppercase tracking-wider text-muted-foreground">
        Dettagli
      </h2>
      <dl className="divide-y text-sm">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4 px-4 py-2">
            <dt className="text-muted-foreground">{k}</dt>
            <dd className="num text-right">{v}</dd>
          </div>
        ))}
      </dl>
      {item.synthetic && (
        <p className="border-t px-4 py-3 text-xs leading-relaxed text-warn">
          Serie sintetica: ricavata dal sottostante con leva {leverageLabel(item.leverage)} e
          ribilanciamento giornaliero, inclusi TER e costo di finanziamento stimati. Non è il prezzo
          di borsa dello strumento: verifica ticker e quotazione su Trading 212 prima di operare.
        </p>
      )}
    </section>
  );
}

const TF_LABEL: Record<string, string> = { "1d": "Giornaliero", "15m": "15 minuti", "5m": "5 minuti" };

function DataQuality({ checks }: { checks: QualityItem[] }) {
  return (
    <section aria-labelledby="qualita" className="rounded-md border bg-card">
      <h2 id="qualita" className="border-b px-4 py-2 text-2xs font-medium uppercase tracking-wider text-muted-foreground">
        Qualità dei dati
      </h2>
      {checks.length === 0 ? (
        <p className="px-4 py-3 text-xs text-muted-foreground">Controllo non disponibile.</p>
      ) : (
        <ul className="divide-y text-sm">
          {checks.map((q) => (
            <li key={q.timeframe} className="flex items-center justify-between gap-3 px-4 py-2">
              <span>
                {TF_LABEL[q.timeframe] ?? q.timeframe}
                <span className="num ml-2 text-2xs text-subtle">{q.rows.toLocaleString("it-IT")} candele</span>
              </span>
              {q.complete ? (
                <span className="text-xs text-up">Completo</span>
              ) : (
                <span className="num text-xs text-warn">{q.missing} mancanti</span>
              )}
            </li>
          ))}
        </ul>
      )}
      {checks.some((q) => q.outliers.length > 0) && (
        <p className="border-t px-4 py-2 text-2xs text-subtle">
          Movimenti estremi segnalati per verifica (ad esempio marzo 2020): non sono errori.
        </p>
      )}
    </section>
  );
}
