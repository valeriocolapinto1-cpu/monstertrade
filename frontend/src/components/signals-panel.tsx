"use client";

import { Minus, Plus } from "lucide-react";
import { useState } from "react";

import { RiskBadge } from "@/components/risk-badge";
import { ScoreBar } from "@/components/score-bar";
import type { Horizon, Signal } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

const HORIZONS: { value: Horizon; label: string; detail: string }[] = [
  { value: "swing", label: "Swing", detail: "giorni / settimane · candele giornaliere" },
  { value: "day", label: "Day trading", detail: "candele da 15 minuti" },
  { value: "long", label: "Lungo periodo", detail: "candele settimanali" },
];

const COMPONENT_LABEL: Record<string, string> = {
  trend: "Trend",
  momentum: "Momentum",
  volume: "Volumi",
  sentiment: "Sentiment",
};

export function SignalsPanel({ signals, underlying }: { signals: Signal[]; underlying?: string | null }) {
  const [horizon, setHorizon] = useState<Horizon>("swing");
  const current = signals.find((s) => s.horizon === horizon);
  const meta = HORIZONS.find((h) => h.value === horizon);

  return (
    <section aria-labelledby="score" className="rounded-md border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-2">
        <h2 id="score" className="text-2xs font-medium uppercase tracking-wider text-muted-foreground">
          Score e segnali
        </h2>
        <div role="tablist" aria-label="Orizzonte" className="flex gap-0.5">
          {HORIZONS.map((h) => (
            <button
              key={h.value}
              type="button"
              role="tab"
              aria-selected={horizon === h.value}
              onClick={() => setHorizon(h.value)}
              className={cn(
                "rounded-sm px-2 py-1 text-xs transition-colors",
                horizon === h.value ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {h.label}
            </button>
          ))}
        </div>
      </div>
      {!current ? (
        <p className="px-4 py-6 text-center text-xs text-muted-foreground">
          Nessuno score per questo orizzonte: servono più dati.
        </p>
      ) : (
        <div className="grid gap-x-6 gap-y-4 px-4 py-4 md:grid-cols-[minmax(0,240px)_1fr]">
          <div className="space-y-3">
            <div className="flex items-end justify-between gap-3">
              <p
                className={cn(
                  "num text-3xl font-medium leading-none tracking-tight",
                  current.score > 0 ? "text-up" : current.score < 0 ? "text-down" : "",
                )}
              >
                {current.score > 0 ? "+" : ""}
                {formatNumber(current.score, 0)}
              </p>
              <RiskBadge label={current.risk_label} />
            </div>
            <ScoreBar value={current.score} label="Score" />
            <p className="text-2xs text-subtle">{meta?.detail} · scala da −100 a +100</p>
            <dl className="space-y-2 pt-1">
              {Object.entries(COMPONENT_LABEL).map(([key, label]) => {
                const value = current.components[key] ?? null;
                return (
                  <div key={key} className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <dt className="text-muted-foreground">
                        {label} <span className="num text-subtle">· peso {formatNumber((current.weights[key] ?? 0) * 100, 0)}%</span>
                      </dt>
                      <dd className="num">{value === null ? "—" : formatNumber(value * 100, 0)}</dd>
                    </div>
                    <ScoreBar value={value === null ? null : value * 100} label={label} className="h-1" />
                  </div>
                );
              })}
            </dl>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <SignalList title="A favore dell'acquisto" tone="up" entries={current.favorable} />
            <SignalList title="Contrari all'acquisto" tone="down" entries={current.contrary} />
          </div>
        </div>
      )}
      <p className="border-t px-4 py-2 text-2xs leading-relaxed text-subtle">
        {underlying
          ? `Segnali calcolati sul sottostante ${underlying}: le descrizioni si riferiscono a ${underlying}, il segno è già quello dello strumento.`
          : "Segnali calcolati sullo strumento."}{" "}
        I segnali con peso 0 sono mostrati per completezza ma non spostano lo score.
      </p>
    </section>
  );
}

function SignalList({
  title,
  tone,
  entries,
}: {
  title: string;
  tone: "up" | "down";
  entries: Signal["favorable"];
}) {
  const Icon = tone === "up" ? Plus : Minus;
  return (
    <div>
      <h3 className="mb-1.5 flex items-center gap-1.5 text-2xs uppercase tracking-wider text-subtle">
        <Icon aria-hidden className={cn("size-3", tone === "up" ? "text-up" : "text-down")} />
        {title}
        <span className="num">{entries.length}</span>
      </h3>
      {entries.length === 0 ? (
        <p className="text-xs text-subtle">Nessuno.</p>
      ) : (
        <ul className="space-y-1.5 text-xs">
          {entries.map((e) => (
            <li key={e.key} className="flex items-baseline justify-between gap-3">
              <span>
                {e.label}
                <span className="ml-1.5 text-2xs text-subtle">{COMPONENT_LABEL[e.component]}</span>
              </span>
              <span className="num text-muted-foreground">{formatNumber(Math.abs(e.value), 2)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
