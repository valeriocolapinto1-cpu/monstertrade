import { ChevronLeft } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Badge } from "@/components/badge";
import { Change } from "@/components/change";
import { PriceChart } from "@/components/price-chart";
import { getInstruments, getQuality, type Instrument, type QualityItem, SYMBOL_PATTERN } from "@/lib/api";
import { formatDate, formatPrice } from "@/lib/format";
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
  const [instruments, quality] = await Promise.all([
    getInstruments(),
    getQuality().catch(() => null),
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
          <DataQuality checks={checks} />
        </aside>
      </div>
    </div>
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
