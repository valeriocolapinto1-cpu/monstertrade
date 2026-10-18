import type { Metadata } from "next";
import Link from "next/link";

import { Badge } from "@/components/badge";
import { Kpi, KpiStrip } from "@/components/kpi";
import { type BrokerPortfolio, getBrokerPortfolio, getPortfolio } from "@/lib/api";
import { formatEur, formatNumber, formatPercent, formatPrice } from "@/lib/format";
import { leverageLabel } from "@/lib/instruments";
import { HORIZON_SHORT } from "@/lib/labels";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Portafoglio" };

export default async function PortafoglioPage() {
  const [p, broker] = await Promise.all([
    getPortfolio(),
    getBrokerPortfolio().catch((e: unknown) => ({ configured: true, error: String(e) }) as BrokerPortfolio & { error?: string }),
  ]);
  const loss = Math.max(-p.day_pnl, 0);
  const symbols = p.positions.map((x) => x.symbol);
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight">Portafoglio e rischio</h1>
        <p className="text-xs text-muted-foreground">Conto reale in sola lettura e simulazione</p>
      </div>
      <RealAccount data={broker} />

      <h2 className="pt-2 text-2xs font-medium uppercase tracking-wider text-muted-foreground">Simulazione</h2>
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

function RealAccount({ data }: { data: BrokerPortfolio & { error?: string } }) {
  if (!data.configured) {
    return (
      <p className="rounded-md border bg-card px-4 py-3 text-xs text-muted-foreground">
        Conto Trading 212 non collegato. Imposta T212_API_KEY e T212_API_SECRET sull&apos;API (solo lettura) per
        calcolare il rischio sul conto reale.
      </p>
    );
  }
  if (data.error || !data.summary || !data.risk) {
    return (
      <p role="alert" className="rounded-md border border-warn/40 bg-warn-muted px-4 py-3 text-xs text-warn">
        Conto Trading 212 non raggiungibile: il rischio si calcola sulla simulazione finché non torna disponibile.
      </p>
    );
  }
  const { summary, risk } = data;
  const loss = Math.max(-risk.day_pnl, 0);
  return (
    <section aria-labelledby="conto" className="space-y-3">
      <h2 id="conto" className="flex items-center gap-2 text-2xs font-medium uppercase tracking-wider text-muted-foreground">
        Conto Trading 212 · {data.env === "live" ? "reale" : "demo"}
        <span className="rounded-sm border border-border-strong px-1 py-px normal-case tracking-normal">sola lettura</span>
      </h2>
      <KpiStrip>
        <Kpi label="Valore del conto" value={formatEur(summary.total)} sub={`liquidità ${formatEur(summary.cash)}`} />
        <Kpi
          label="Risultato del giorno"
          value={formatEur(risk.day_pnl)}
          sub={`limite ${formatEur(risk.day_pnl_limit)}`}
          tone={risk.day_pnl < 0 ? "down" : risk.day_pnl > 0 ? "up" : undefined}
          meter={{ value: loss, max: -risk.day_pnl_limit, warn: risk.daily_limit_reached }}
        />
        <Kpi
          label="Esposizione leva 3x"
          value={formatEur(risk.lev3_exposure)}
          sub={`limite ${formatEur(risk.lev3_limit)}`}
          meter={{ value: risk.lev3_exposure, max: risk.lev3_limit, warn: risk.lev3_exposure > risk.lev3_limit }}
        />
        <Kpi
          label="Posizioni"
          value={`${risk.positions} / ${risk.max_positions}`}
          sub={`rischio per trade ${formatEur(risk.risk_per_trade)}`}
          meter={{ value: risk.positions, max: risk.max_positions, warn: risk.positions > risk.max_positions }}
        />
      </KpiStrip>
      {data.positions && data.positions.length > 0 && (
        <div className="overflow-x-auto rounded-md border bg-card">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="text-2xs uppercase tracking-wider text-subtle">
                <th scope="col" className="px-4 py-2 text-left font-medium">Ticker</th>
                <th scope="col" className="px-2 py-2 text-right font-medium">Quantità</th>
                <th scope="col" className="px-2 py-2 text-right font-medium">Prezzo medio</th>
                <th scope="col" className="px-2 py-2 text-right font-medium">Attuale</th>
                <th scope="col" className="px-2 py-2 text-right font-medium">Valore</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Risultato</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.positions.map((x) => (
                <tr key={x.ticker}>
                  <th scope="row" className="px-4 py-2.5 text-left font-normal">
                    <span className="num">{x.ticker}</span>
                    <span className="block text-2xs text-subtle">
                      {x.name ? `${x.name}${x.leverage && x.leverage !== 1 ? ` · ${leverageLabel(x.leverage)}` : ""}` : "fuori dall'universo"}
                    </span>
                  </th>
                  <td className="num px-2 py-2.5 text-right">{formatNumber(x.quantity, 4)}</td>
                  <td className="num px-2 py-2.5 text-right">{formatPrice(x.average_price)}</td>
                  <td className="num px-2 py-2.5 text-right">{formatPrice(x.current_price)}</td>
                  <td className="num px-2 py-2.5 text-right">{formatEur(x.value)}</td>
                  <td className={cn("num px-4 py-2.5 text-right", x.pnl >= 0 ? "text-up" : "text-down")}>{formatEur(x.pnl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
