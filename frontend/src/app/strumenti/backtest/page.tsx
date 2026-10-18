import { ChevronLeft } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { HORIZON_LABEL } from "@/components/backtest-table";
import { type BacktestRow, getBacktest } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Backtest" };

function pct(v: number | null): string {
  if (v === null) return "—";
  const s = formatNumber(v * 100, 1);
  return v > 0 ? `+${s}%` : `${s}%`;
}

export default async function BacktestPage() {
  const report = await getBacktest();
  const symbols = [...new Set(report.results.map((r) => r.symbol))];
  const horizons = ["swing", "long", "day"] as const;

  const best = (symbol: string, horizon: BacktestRow["horizon"]) => {
    const rows = report.results.filter((r) => r.symbol === symbol && r.horizon === horizon);
    const strategies = rows.filter((r) => r.family !== "riferimento");
    const top = strategies.sort((a, b) => (b.total_return ?? -9) - (a.total_return ?? -9))[0];
    const hold = rows.find((r) => r.family === "riferimento");
    return { top, hold };
  };

  return (
    <div className="space-y-5">
      <Link href="/strumenti" className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
        <ChevronLeft aria-hidden className="size-3.5" />
        Strumenti
      </Link>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight">Backtest</h1>
        <p className="num text-xs text-muted-foreground">aggiornato {formatDate(report.generated_at)}</p>
      </div>
      <div
        className={cn(
          "rounded-md border px-4 py-3 text-sm",
          report.criterion_met ? "border-up/30 bg-up-muted" : "border-warn/30 bg-warn-muted",
        )}
      >
        <p className="font-medium">
          {report.criterion_met
            ? "Criterio della Fase 2 soddisfatto"
            : "Criterio della Fase 2 non soddisfatto"}
        </p>
        <p className="num mt-0.5 text-xs text-muted-foreground">
          {report.positive_strategies} strategie su {report.tested_strategies} con risultato positivo dopo i
          costi sullo storico. Nel day trading nessuna strategia batte i costi: spread e cambio valuta pesano
          troppo su capitali piccoli.
        </p>
      </div>
      {horizons.map((h) => (
        <section key={h} aria-labelledby={`h-${h}`} className="overflow-x-auto rounded-md border bg-card">
          <h2 id={`h-${h}`} className="border-b px-4 py-2 text-2xs font-medium uppercase tracking-wider text-muted-foreground">
            {HORIZON_LABEL[h]}
          </h2>
          <table className="w-full min-w-[640px] text-xs">
            <thead>
              <tr className="text-2xs text-subtle">
                <th scope="col" className="px-4 py-1.5 text-left font-normal">Strumento</th>
                <th scope="col" className="px-2 py-1.5 text-left font-normal">Migliore strategia</th>
                <th scope="col" className="px-2 py-1.5 text-right font-normal">
                  {h === "day" ? "Totale 60 g" : "Annuo"}
                </th>
                <th scope="col" className="px-2 py-1.5 text-right font-normal">Drawdown</th>
                <th scope="col" className="px-2 py-1.5 text-right font-normal">Sharpe</th>
                <th scope="col" className="px-4 py-1.5 text-right font-normal">
                  Compra e tieni{h === "day" ? " · 60 g" : ""}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {symbols.map((s) => {
                const { top, hold } = best(s, h);
                if (!top) return null;
                // Sul day trading (60 giorni) un rendimento annualizzato sarebbe fuorviante.
                const shown = h === "day" ? top.total_return : top.cagr;
                const holdShown = h === "day" ? (hold?.total_return ?? null) : (hold?.cagr ?? null);
                return (
                  <tr key={s} className="hover:bg-surface-hover">
                    <th scope="row" className="px-4 py-1.5 text-left font-normal">
                      <Link href={`/strumenti/${s}`} className="num hover:text-primary">{s}</Link>
                    </th>
                    <td className="px-2 py-1.5 text-muted-foreground">{top.strategy_name}</td>
                    <td className={cn("num px-2 py-1.5 text-right", (shown ?? 0) > 0 ? "text-up" : "text-down")}>
                      {pct(shown)}
                    </td>
                    <td className="num px-2 py-1.5 text-right text-down">{pct(top.max_drawdown)}</td>
                    <td className="num px-2 py-1.5 text-right">{top.sharpe === null ? "—" : formatNumber(top.sharpe, 2)}</td>
                    <td className="num px-4 py-1.5 text-right text-muted-foreground">{pct(holdShown)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      ))}
      <p className="text-2xs leading-relaxed text-subtle">
        Le serie degli ETF a leva sono sintetiche dal 2000 (gli strumenti reali sono più recenti) e gli indici
        sono di prezzo, senza dividendi. Nessun parametro è stato ottimizzato: le strategie sono fisse, per
        ridurre il rischio di adattarsi al passato.
      </p>
    </div>
  );
}
