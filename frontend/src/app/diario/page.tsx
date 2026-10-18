import type { Metadata } from "next";
import Link from "next/link";

import { Kpi, KpiStrip } from "@/components/kpi";
import { RiskBadge } from "@/components/risk-badge";
import { getJournal } from "@/lib/api";
import { formatDate, formatEur, formatNumber, formatPrice } from "@/lib/format";
import { EXIT_LABEL, HORIZON_SHORT, STATUS_LABEL } from "@/lib/labels";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Diario" };

function pct(v: number | null, digits = 0): string {
  return v === null ? "—" : `${formatNumber(v * 100, digits)}%`;
}

export default async function DiarioPage() {
  const { stats, items } = await getJournal();
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight">Diario dei consigli</h1>
        <p className="text-xs text-muted-foreground">Tutte le proposte con il loro esito simulato</p>
      </div>
      <KpiStrip>
        <Kpi label="Operazioni chiuse" value={stats.trades} sub={`costi pagati ${formatEur(stats.fees)}`} />
        <Kpi label="Percentuale di successo" value={pct(stats.win_rate)} />
        <Kpi
          label="Guadagno medio"
          value={stats.avg_pnl === null ? "—" : formatEur(stats.avg_pnl)}
          sub={stats.avg_pnl_pct === null ? undefined : `${formatNumber(stats.avg_pnl_pct, 2)}% per operazione`}
          tone={(stats.avg_pnl ?? 0) > 0 ? "up" : (stats.avg_pnl ?? 0) < 0 ? "down" : undefined}
        />
        <Kpi
          label="Risultato totale"
          value={formatEur(stats.total_pnl)}
          sub={`drawdown max ${pct(stats.max_drawdown, 1)}`}
          tone={stats.total_pnl > 0 ? "up" : stats.total_pnl < 0 ? "down" : undefined}
        />
      </KpiStrip>
      <p className="text-2xs leading-relaxed text-subtle">
        Il criterio per passare a Trading 212 è avere mesi di risultati positivi dopo i costi in questo diario.
        Poche settimane non bastano a distinguere l&apos;abilità dal caso.
      </p>
      <section aria-labelledby="storico" className="overflow-x-auto rounded-md border bg-card">
        <h2 id="storico" className="border-b px-4 py-2 text-2xs font-medium uppercase tracking-wider text-muted-foreground">
          Storico
        </h2>
        {items.length === 0 ? (
          <p className="px-4 py-8 text-center text-xs text-muted-foreground">
            Il diario si riempie con le prime proposte.
          </p>
        ) : (
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr className="text-2xs uppercase tracking-wider text-subtle">
                <th scope="col" className="px-4 py-2 text-left font-medium">Data</th>
                <th scope="col" className="px-2 py-2 text-left font-medium">Strumento</th>
                <th scope="col" className="px-2 py-2 text-left font-medium">Stato</th>
                <th scope="col" className="px-2 py-2 text-right font-medium">Ingresso</th>
                <th scope="col" className="px-2 py-2 text-right font-medium">Uscita</th>
                <th scope="col" className="px-2 py-2 text-right font-medium">Importo</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Esito</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {items.map((i) => (
                <tr key={i.id}>
                  <td className="num px-4 py-2.5 text-xs text-muted-foreground">{formatDate(i.created_at)}</td>
                  <th scope="row" className="px-2 py-2.5 text-left font-normal">
                    <Link href={`/strumenti/${i.symbol}`} className="hover:text-primary">{i.name}</Link>
                    <span className="mt-0.5 flex items-center gap-1.5 text-2xs text-subtle">
                      <span>{HORIZON_SHORT[i.horizon]}</span>
                      <RiskBadge label={i.risk_label} />
                    </span>
                  </th>
                  <td className="px-2 py-2.5 text-xs">
                    {STATUS_LABEL[i.status]}
                    {i.exit_reason && <span className="block text-2xs text-subtle">{EXIT_LABEL[i.exit_reason]}</span>}
                  </td>
                  <td className="num px-2 py-2.5 text-right">{formatPrice(i.entry_price ?? i.entry)}</td>
                  <td className="num px-2 py-2.5 text-right">{i.exit_price === null ? "—" : formatPrice(i.exit_price)}</td>
                  <td className="num px-2 py-2.5 text-right">{formatEur(i.size_eur)}</td>
                  <td className={cn("num px-4 py-2.5 text-right", i.pnl_eur === null ? "text-subtle" : i.pnl_eur >= 0 ? "text-up" : "text-down")}>
                    {i.pnl_eur === null ? "—" : formatEur(i.pnl_eur)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
