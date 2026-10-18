import type { Metadata } from "next";
import Link from "next/link";

import { Badge } from "@/components/badge";
import { Kpi, KpiStrip } from "@/components/kpi";
import { getPortfolio } from "@/lib/api";
import { formatEur, formatNumber, formatPercent, formatPrice } from "@/lib/format";
import { leverageLabel } from "@/lib/instruments";
import { HORIZON_SHORT } from "@/lib/labels";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Portafoglio" };

export default async function PortafoglioPage() {
  const p = await getPortfolio();
  const loss = Math.max(-p.day_pnl, 0);
  const symbols = p.positions.map((x) => x.symbol);
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight">Portafoglio e rischio</h1>
        <p className="text-xs text-muted-foreground">Posizioni simulate · prezzi di chiusura</p>
      </div>
      <KpiStrip>
        <Kpi
          label="Capitale"
          value={formatEur(p.equity)}
          sub={`investito ${formatEur(p.invested)} · liquidità ${formatEur(p.cash)}`}
        />
        <Kpi
          label="Risultato del giorno"
          value={formatEur(p.day_pnl)}
          sub={`limite ${formatEur(p.day_pnl_limit)}`}
          tone={p.day_pnl < 0 ? "down" : p.day_pnl > 0 ? "up" : undefined}
          meter={{ value: loss, max: -p.day_pnl_limit, warn: loss > -p.day_pnl_limit * 0.66 }}
        />
        <Kpi
          label="Esposizione leva 3x"
          value={formatEur(p.lev3_exposure)}
          sub={`limite ${formatEur(p.lev3_limit)} (30%)`}
          meter={{ value: p.lev3_exposure, max: p.lev3_limit, warn: p.lev3_exposure > p.lev3_limit * 0.8 }}
        />
        <Kpi label="Posizioni" value={`${p.positions.length} / 3`} meter={{ value: p.positions.length, max: 3 }} />
      </KpiStrip>

      <section aria-labelledby="posizioni" className="overflow-x-auto rounded-md border bg-card">
        <h2 id="posizioni" className="border-b px-4 py-2 text-2xs font-medium uppercase tracking-wider text-muted-foreground">
          Posizioni aperte
        </h2>
        {p.positions.length === 0 ? (
          <p className="px-4 py-8 text-center text-xs text-muted-foreground">
            Nessuna posizione aperta. Le proposte della pagina Oggi vengono aperte in simulazione alla candela
            successiva.
          </p>
        ) : (
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="text-2xs uppercase tracking-wider text-subtle">
                <th scope="col" className="px-4 py-2 text-left font-medium">Strumento</th>
                <th scope="col" className="px-2 py-2 text-right font-medium">Ingresso</th>
                <th scope="col" className="px-2 py-2 text-right font-medium">Ultimo</th>
                <th scope="col" className="px-2 py-2 text-right font-medium">Stop</th>
                <th scope="col" className="px-2 py-2 text-right font-medium">Obiettivo</th>
                <th scope="col" className="px-2 py-2 text-right font-medium">Valore</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Risultato</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {p.positions.map((x) => {
                const lev = leverageLabel(x.leverage);
                return (
                  <tr key={x.symbol}>
                    <th scope="row" className="px-4 py-2.5 text-left font-normal">
                      <Link href={`/strumenti/${x.symbol}`} className="font-medium hover:text-primary">{x.name}</Link>
                      <span className="mt-0.5 flex items-center gap-1.5 text-2xs text-subtle">
                        <span className="num">{x.symbol}</span>
                        {lev && <Badge tone={x.leverage < 0 ? "down" : "neutral"}>{lev}</Badge>}
                        <span>{HORIZON_SHORT[x.horizon]}</span>
                      </span>
                    </th>
                    <td className="num px-2 py-2.5 text-right">{formatPrice(x.entry_price)}</td>
                    <td className="num px-2 py-2.5 text-right">{formatPrice(x.last_price)}</td>
                    <td className="num px-2 py-2.5 text-right text-down">{formatPrice(x.stop)}</td>
                    <td className="num px-2 py-2.5 text-right text-up">{formatPrice(x.target)}</td>
                    <td className="num px-2 py-2.5 text-right">{formatEur(x.value)}</td>
                    <td className={cn("num px-4 py-2.5 text-right", x.pnl >= 0 ? "text-up" : "text-down")}>
                      {formatEur(x.pnl)}
                      <span className="block text-2xs">{formatPercent(x.pnl_pct)}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      {symbols.length > 1 && (
        <section aria-labelledby="corr" className="overflow-x-auto rounded-md border bg-card">
          <h2 id="corr" className="border-b px-4 py-2 text-2xs font-medium uppercase tracking-wider text-muted-foreground">
            Correlazioni tra le posizioni · 90 giorni
          </h2>
          <table className="text-xs">
            <thead>
              <tr>
                <td />
                {symbols.map((s) => (
                  <th key={s} scope="col" className="num px-3 py-2 text-right font-normal text-subtle">{s}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {symbols.map((a) => (
                <tr key={a}>
                  <th scope="row" className="num px-4 py-1.5 text-left font-normal text-subtle">{a}</th>
                  {symbols.map((b) => {
                    const v = a === b ? 1 : (p.correlations[a]?.[b] ?? null);
                    return (
                      <td key={b} className={cn("num px-3 py-1.5 text-right", v !== null && Math.abs(v) > 0.8 && a !== b && "text-warn")}>
                        {v === null ? "—" : formatNumber(v, 2)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
