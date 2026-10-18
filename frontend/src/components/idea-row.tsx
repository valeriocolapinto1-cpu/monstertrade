import { AlertTriangle } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/badge";
import { OrderButton } from "@/components/order-button";
import { RiskBadge } from "@/components/risk-badge";
import type { Idea } from "@/lib/api";
import { formatEur, formatNumber, formatPrice } from "@/lib/format";
import { leverageLabel } from "@/lib/instruments";
import { HORIZON_SHORT } from "@/lib/labels";

/** `orderMode` presente solo se gli ordini sono abilitati e il blocco totale è disattivato. */
export function IdeaRow({ idea, orderMode }: { idea: Idea; orderMode?: "demo" | "live" }) {
  const lev = leverageLabel(idea.leverage);
  const stopPct = (idea.stop / idea.entry - 1) * 100;
  const targetPct = (idea.target / idea.entry - 1) * 100;
  const [first, second] = idea.motivation.split("\n");
  const levels: [string, string, string?, string?][] = [
    ["Ingresso", formatPrice(idea.entry)],
    ["Stop", formatPrice(idea.stop), `${formatNumber(stopPct, 1)}%`, "text-down"],
    ["Obiettivo", formatPrice(idea.target), `+${formatNumber(targetPct, 1)}%`, "text-up"],
    ["Importo", formatEur(idea.size_eur)],
    ["Rischio", formatEur(idea.risk_eur), "costi inclusi"],
    ["Costi", formatEur(idea.costs_eur), "andata e ritorno"],
  ];
  return (
    <article className="grid gap-x-6 gap-y-3 px-4 py-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Link href={`/strumenti/${idea.symbol}`} className="font-medium hover:text-primary">
            {idea.name}
          </Link>
          <span className="num text-2xs text-subtle">{idea.symbol}</span>
          {lev && <Badge tone={idea.leverage < 0 ? "down" : "neutral"}>{lev}</Badge>}
          <RiskBadge label={idea.risk_label} />
        </div>
        <p className="text-2xs uppercase tracking-wider text-subtle">
          {HORIZON_SHORT[idea.horizon]} · score{" "}
          <span className="num text-up">+{formatNumber(idea.score, 0)}</span>
        </p>
        <p className="text-sm leading-relaxed">{first}</p>
        {second && <p className="text-xs leading-relaxed text-muted-foreground">{second}</p>}
        {idea.warnings.length > 0 && (
          <ul className="space-y-1 pt-1">
            {idea.warnings.map((w) => (
              <li key={w} className="flex items-start gap-1.5 text-2xs text-warn">
                <AlertTriangle aria-hidden className="mt-px size-3 shrink-0" />
                {w}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="space-y-2 self-start">
        <dl className="grid grid-cols-3 gap-x-4 gap-y-3 rounded-sm border bg-background/40 px-3 py-2.5">
          {levels.map(([label, value, sub, tone]) => (
            <div key={label} className="text-right">
              <dt className="text-2xs uppercase tracking-wider text-subtle">{label}</dt>
              <dd className="num text-sm">{value}</dd>
              {sub && <dd className={`num text-2xs ${tone ?? "text-subtle"}`}>{sub}</dd>}
            </div>
          ))}
        </dl>
        {orderMode && idea.orderable && (
          <div className="flex justify-end">
            <OrderButton ideaId={idea.id} mode={orderMode} />
          </div>
        )}
      </div>
    </article>
  );
}
