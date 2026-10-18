import { formatNumber } from "@/lib/format";
import { RISK_CARDS } from "@/lib/indicator-cards";

type Metric = { label: string; value: string; tone?: "down" | "warn"; hint: string };

function pct(v: number | null | undefined, digits = 1): string {
  return v === null || v === undefined ? "—" : `${formatNumber(v * 100, digits)}%`;
}

export function RiskPanel({
  metrics,
  latest,
  leverage,
}: {
  metrics: Record<string, number | null>;
  latest: Record<string, number | null>;
  leverage: number;
}) {
  const decay = latest.decay_annual;
  const adx = latest.adx;
  const lateral = adx !== null && adx !== undefined && adx < 20;
  const items: Metric[] = [
    {
      label: RISK_CARDS.drawdown.name,
      value: pct(metrics.max_drawdown),
      tone: "down",
      hint: RISK_CARDS.drawdown.measures,
    },
    {
      label: RISK_CARDS.sharpe.name,
      value: metrics.sharpe === null || metrics.sharpe === undefined ? "—" : formatNumber(metrics.sharpe, 2),
      hint: RISK_CARDS.sharpe.reading,
    },
    { label: "Volatilità annua", value: pct(metrics.volatility), hint: "Deviazione standard dei rendimenti, annualizzata." },
    { label: RISK_CARDS.rvol.name, value: pct(latest.rvol_20), hint: RISK_CARDS.rvol.measures },
  ];
  if (leverage !== 1) {
    items.push({
      label: RISK_CARDS.decay.name,
      value: decay === null || decay === undefined ? "—" : `−${formatNumber(decay * 100, 1)}% / anno`,
      tone: "warn",
      hint: RISK_CARDS.decay.reading,
    });
  }
  return (
    <section aria-labelledby="rischio" className="rounded-md border bg-card">
      <h2 id="rischio" className="border-b px-4 py-2 text-2xs font-medium uppercase tracking-wider text-muted-foreground">
        Rischio · ultimi 12 mesi
      </h2>
      <dl className="divide-y text-sm">
        {items.map((m) => (
          <div key={m.label} className="px-4 py-2" title={m.hint}>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">{m.label}</dt>
              <dd className={`num text-right ${m.tone === "down" ? "text-down" : m.tone === "warn" ? "text-warn" : ""}`}>
                {m.value}
              </dd>
            </div>
          </div>
        ))}
      </dl>
      {leverage !== 1 && lateral && (
        <p role="note" className="border-t bg-warn-muted px-4 py-2.5 text-xs leading-relaxed text-warn">
          Mercato laterale (ADX {formatNumber(adx ?? 0, 0)}): il decadimento della leva pesa di più. Evita di
          tenere la posizione a lungo.
        </p>
      )}
    </section>
  );
}
