import type { BacktestRow } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

export const HORIZON_LABEL: Record<BacktestRow["horizon"], string> = {
  day: "Day trading · 15 minuti, ultimi 60 giorni",
  swing: "Swing · giornaliero",
  long: "Lungo periodo · settimanale",
};

function pct(v: number | null, digits = 1, signed = true): string {
  if (v === null) return "—";
  const s = formatNumber(v * 100, digits);
  return signed && v > 0 ? `+${s}%` : `${s}%`;
}

function tone(v: number | null): string {
  if (v === null) return "text-subtle";
  return v > 0 ? "text-up" : v < 0 ? "text-down" : "text-muted-foreground";
}

export function BacktestTable({ rows }: { rows: BacktestRow[] }) {
  const horizons = (["swing", "long", "day"] as const).filter((h) => rows.some((r) => r.horizon === h));
  if (horizons.length === 0) {
    return <p className="px-4 py-3 text-xs text-muted-foreground">Nessun backtest disponibile.</p>;
  }
  return (
    <div className="divide-y">
      {horizons.map((h) => {
        const group = rows.filter((r) => r.horizon === h);
        return (
          <div key={h} className="overflow-x-auto">
            <p className="px-4 pb-1 pt-3 text-2xs uppercase tracking-wider text-subtle">
              {HORIZON_LABEL[h]} · {group[0]?.start} → {group[0]?.end}
            </p>
            <table className="w-full min-w-[640px] text-xs">
              <thead>
                <tr className="text-2xs text-subtle">
                  <th scope="col" className="px-4 py-1.5 text-left font-normal">Strategia</th>
                  <th scope="col" className="px-2 py-1.5 text-right font-normal">Totale</th>
                  <th scope="col" className="px-2 py-1.5 text-right font-normal">{h === "day" ? "" : "Annuo"}</th>
                  <th scope="col" className="px-2 py-1.5 text-right font-normal">Sharpe</th>
                  <th scope="col" className="px-2 py-1.5 text-right font-normal">Drawdown max</th>
                  <th scope="col" className="px-2 py-1.5 text-right font-normal">Operazioni</th>
                  <th scope="col" className="px-2 py-1.5 text-right font-normal">Vincenti</th>
                  <th scope="col" className="px-4 py-1.5 text-right font-normal">Costi</th>
                </tr>
              </thead>
              <tbody>
                {group.map((r) => (
                  <tr
                    key={r.strategy}
                    className={cn(
                      r.family === "riferimento" && "text-muted-foreground",
                      r.family === "score" && "bg-surface-hover",
                    )}
                  >
                    <th scope="row" className="px-4 py-1.5 text-left font-normal">
                      {r.strategy_name}
                      {r.family === "riferimento" && <span className="ml-1 text-subtle">(riferimento)</span>}
                    </th>
                    <td className={cn("num px-2 py-1.5 text-right", tone(r.total_return))}>{pct(r.total_return, 0)}</td>
                    <td className={cn("num px-2 py-1.5 text-right", tone(r.cagr))}>
                      {h === "day" ? "" : pct(r.cagr)}
                    </td>
                    <td className="num px-2 py-1.5 text-right">{r.sharpe === null ? "—" : formatNumber(r.sharpe, 2)}</td>
                    <td className="num px-2 py-1.5 text-right text-down">{pct(r.max_drawdown, 0, false)}</td>
                    <td className="num px-2 py-1.5 text-right">{r.trades}</td>
                    <td className="num px-2 py-1.5 text-right">
                      {r.family === "riferimento" ? "—" : pct(r.win_rate, 0, false)}
                    </td>
                    <td className="num px-4 py-1.5 text-right text-muted-foreground">{pct(r.costs_paid, 1, false)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}
