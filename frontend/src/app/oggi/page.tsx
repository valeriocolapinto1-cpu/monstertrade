import { AlertTriangle } from "lucide-react";
import type { Metadata } from "next";

import { IdeaRow } from "@/components/idea-row";
import { Kpi, KpiStrip } from "@/components/kpi";
import { getToday } from "@/lib/api";
import { formatEur, formatNumber } from "@/lib/format";
import { HORIZON_SHORT } from "@/lib/labels";

export const metadata: Metadata = { title: "Oggi" };

export default async function OggiPage() {
  const t = await getToday();
  const limit = t.limits.max_daily_loss * t.capital;
  const loss = Math.max(-t.day_pnl, 0);
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-xl font-semibold tracking-tight">Oggi</h1>
        <p className="text-xs text-muted-foreground">
          Rischio calcolato su: {t.risk_source === "conto" ? "conto Trading 212 (sola lettura)" : "simulazione"} ·
          nessun ordine viene inviato al broker
        </p>
      </div>
      <KpiStrip>
        <Kpi
          label={t.risk_source === "conto" ? "Conto a inizio giornata" : "Capitale simulato"}
          value={formatEur(t.equity)}
          sub={`iniziale ${formatEur(t.capital)}`}
          tone={t.equity > t.capital ? "up" : t.equity < t.capital ? "down" : undefined}
        />
        <Kpi
          label="Risultato del giorno"
          value={formatEur(t.day_pnl)}
          sub={`limite −${formatEur(limit)} (${formatNumber(t.limits.max_daily_loss * 100, 0)}%)`}
          tone={t.day_pnl < 0 ? "down" : t.day_pnl > 0 ? "up" : undefined}
          meter={{ value: loss, max: limit, warn: loss > limit * 0.66 }}
        />
        <Kpi
          label="Posizioni e proposte"
          value={`${t.open_positions} / ${t.limits.max_open_positions}`}
          meter={{ value: t.open_positions, max: t.limits.max_open_positions }}
        />
        <Kpi
          label="Rischio per trade"
          value={formatEur(t.capital * t.limits.risk_per_trade)}
          sub={`${formatNumber(t.limits.risk_per_trade * 100, 0)}% del capitale`}
        />
      </KpiStrip>

      {t.daily_limit_reached && (
        <p role="alert" className="flex items-start gap-2 rounded-md border border-warn/40 bg-warn-muted px-4 py-3 text-sm text-warn">
          <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />
          Perdita giornaliera massima raggiunta: nessuna nuova proposta fino a domani.
        </p>
      )}

      <section aria-labelledby="proposte" className="rounded-md border bg-card">
        <h2 id="proposte" className="flex items-baseline justify-between border-b px-4 py-2 text-2xs font-medium uppercase tracking-wider text-muted-foreground">
          Trade proposti
          <span className="num normal-case tracking-normal text-subtle">ordinati per score</span>
        </h2>
        {t.proposals.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <p className="font-medium">Nessuna proposta in questo momento</p>
            <p className="mx-auto mt-1 max-w-md text-xs text-muted-foreground">
              Si propone un trade solo se lo score supera la soglia, il rischio resta nei limiti e conviene
              dopo i costi. Non operare è spesso la scelta migliore.
            </p>
          </div>
        ) : (
          <div className="divide-y">
            {t.proposals.map((idea) => (
              <IdeaRow key={idea.id} idea={idea} />
            ))}
          </div>
        )}
      </section>

      {t.skipped.length > 0 && (
        <section aria-labelledby="scartati" className="rounded-md border bg-card">
          <h2 id="scartati" className="border-b px-4 py-2 text-2xs font-medium uppercase tracking-wider text-muted-foreground">
            Candidati scartati e perché
          </h2>
          <ul className="divide-y text-sm">
            {t.skipped.map((s) => (
              <li key={`${s.symbol}-${s.horizon}`} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-4 py-2">
                <span>
                  {s.name}
                  <span className="num ml-2 text-2xs text-subtle">
                    {s.symbol} · {HORIZON_SHORT[s.horizon]} · score +{formatNumber(s.score, 0)}
                  </span>
                </span>
                <span className="text-xs text-muted-foreground">{s.reason}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
