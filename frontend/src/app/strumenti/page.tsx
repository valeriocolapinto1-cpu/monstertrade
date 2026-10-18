import type { Metadata } from "next";
import Link from "next/link";

import { Badge } from "@/components/badge";
import { Change } from "@/components/change";
import { getInstruments, type Instrument } from "@/lib/api";
import { formatDate, formatPrice } from "@/lib/format";
import { KIND_LABEL, KIND_ORDER, leverageLabel } from "@/lib/instruments";

export const metadata: Metadata = { title: "Strumenti" };

export default async function StrumentiPage() {
  const instruments = await getInstruments();
  const groups = KIND_ORDER.map((kind) => ({
    kind,
    items: instruments.filter((i) => i.kind === kind),
  })).filter((g) => g.items.length > 0);

  return (
    <div className="space-y-5">
      <PageTitle count={instruments.length} />
      {groups.length === 0 ? (
        <EmptyState />
      ) : (
        groups.map((group) => (
          <section
            key={group.kind}
            aria-labelledby={`g-${group.kind}`}
            className="overflow-hidden rounded-md border bg-card"
          >
            <h2
              id={`g-${group.kind}`}
              className="border-b px-4 py-2 text-2xs font-medium uppercase tracking-wider text-muted-foreground"
            >
              {KIND_LABEL[group.kind]}
            </h2>
            <table className="w-full text-sm">
              <thead className="sr-only sm:not-sr-only">
                <tr className="border-b text-2xs uppercase tracking-wider text-subtle">
                  <th scope="col" className="px-4 py-2 text-left font-medium">
                    Strumento
                  </th>
                  <th scope="col" className="hidden px-4 py-2 text-left font-medium md:table-cell">
                    Riferimento
                  </th>
                  <th scope="col" className="px-4 py-2 text-right font-medium">
                    Ultimo
                  </th>
                  <th scope="col" className="px-4 py-2 text-right font-medium">
                    Var. 1G
                  </th>
                  <th scope="col" className="hidden px-4 py-2 text-right font-medium lg:table-cell">
                    Chiusura
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {group.items.map((item) => (
                  <Row key={item.symbol} item={item} />
                ))}
              </tbody>
            </table>
          </section>
        ))
      )}
    </div>
  );
}

function PageTitle({ count }: { count: number }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <h1 className="text-xl font-semibold tracking-tight">Strumenti</h1>
      <p className="num flex items-baseline gap-3 text-xs text-muted-foreground">
        <span>{count} seguiti · chiusure giornaliere</span>
        <Link href="/strumenti/backtest" className="text-primary hover:underline">
          Backtest
        </Link>
      </p>
    </div>
  );
}

function Row({ item }: { item: Instrument }) {
  const lev = leverageLabel(item.leverage);
  return (
    <tr className="group relative transition-colors hover:bg-surface-hover">
      <td className="px-4 py-2.5">
        <Link
          href={`/strumenti/${item.symbol}`}
          className="after:absolute after:inset-0 focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-ring"
        >
          <span className="block font-medium">{item.name}</span>
          <span className="flex items-center gap-1.5 whitespace-nowrap text-2xs text-subtle">
            <span className="num">{item.symbol}</span>
            {lev && <Badge tone={item.leverage < 0 ? "down" : "neutral"}>{lev}</Badge>}
            {item.synthetic && <span className="hidden sm:inline">· sintetico</span>}
          </span>
        </Link>
      </td>
      <td className="hidden px-4 py-2.5 text-xs text-muted-foreground md:table-cell">
        {item.reference_ticker ?? (item.underlying ? `su ${item.underlying}` : "—")}
      </td>
      <td className="num px-4 py-2.5 text-right">
        {item.last_price === null ? "—" : formatPrice(item.last_price)}
        <span className="ml-1 text-2xs text-subtle">{item.synthetic ? "pt" : item.currency}</span>
      </td>
      <td className="px-4 py-2.5 text-right">
        <Change value={item.change_pct} />
      </td>
      <td className="num hidden px-4 py-2.5 text-right text-xs text-muted-foreground lg:table-cell">
        {item.last_ts ? formatDate(item.last_ts) : "—"}
      </td>
    </tr>
  );
}

function EmptyState() {
  return (
    <div className="rounded-md border bg-card px-4 py-10 text-center">
      <p className="font-medium">Nessuno strumento nel database</p>
      <p className="mt-1 text-xs text-muted-foreground">
        Avvia lo scarico dei prezzi: <code className="num">python -m app.jobs.prices update</code>
      </p>
    </div>
  );
}
