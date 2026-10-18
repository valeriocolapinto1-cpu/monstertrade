"use client";

import { AlertTriangle, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import type { OrderPreview, OrderRow } from "@/lib/api";
import { formatEur, formatNumber, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

type Phase =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "preview"; data: OrderPreview; until: number }
  | { kind: "sending"; data: OrderPreview }
  | { kind: "done"; order: OrderRow }
  | { kind: "error"; message: string };

const STATUS_TEXT: Record<OrderRow["status"], string> = {
  in_attesa: "In attesa",
  inviato: "Inviato al broker",
  eseguito: "Eseguito",
  rifiutato: "Rifiutato dal broker",
  incerto: "Esito incerto: verifica nell'app Trading 212 prima di fare altro",
};

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = (await response.json().catch(() => ({}))) as { detail?: unknown };
  if (!response.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : `Richiesta non riuscita (${response.status})`);
  }
  return data as T;
}

/** Ordine su una proposta: anteprima con tutti i controlli, poi un solo tocco di conferma. */
export function OrderButton({ ideaId, mode }: { ideaId: number; mode: "demo" | "live" }) {
  const router = useRouter();
  const dialog = useRef<HTMLDialogElement>(null);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (phase.kind !== "preview") return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [phase.kind]);

  const open = async () => {
    setPhase({ kind: "loading" });
    dialog.current?.showModal();
    try {
      const data = await post<OrderPreview>("/api/ordini/anteprima", { idea_id: ideaId });
      setNow(Date.now());
      setPhase({ kind: "preview", data, until: Date.now() + data.expires_in * 1000 });
    } catch (e) {
      setPhase({ kind: "error", message: (e as Error).message });
    }
  };

  const confirm = async (data: OrderPreview) => {
    setPhase({ kind: "sending", data });
    try {
      const order = await post<OrderRow>("/api/ordini/invia", {
        idea_id: data.idea_id,
        quantity: data.quantity,
        token: data.token,
      });
      setPhase({ kind: "done", order });
    } catch (e) {
      setPhase({ kind: "error", message: (e as Error).message });
    }
  };

  const close = () => {
    dialog.current?.close();
    if (phase.kind === "done") router.refresh();
    setPhase({ kind: "idle" });
  };

  const live = mode === "live";
  const secondsLeft = phase.kind === "preview" ? Math.max(0, Math.ceil((phase.until - now) / 1000)) : 0;

  return (
    <>
      <button
        type="button"
        onClick={open}
        className="h-8 rounded-sm border border-primary/60 px-3 text-xs font-medium text-primary transition-colors hover:bg-primary hover:text-primary-foreground"
      >
        Ordina{live ? "" : " (demo)"}
      </button>
      <dialog
        ref={dialog}
        onClose={close}
        aria-labelledby={`ordine-${ideaId}`}
        className="m-auto w-[min(26rem,calc(100vw-2rem))] rounded-md border border-border-strong bg-popover p-0 text-foreground backdrop:bg-black/60"
      >
        <div
          className={cn(
            "px-4 py-2 text-2xs font-semibold uppercase tracking-wider",
            live ? "bg-warn-muted text-warn" : "bg-primary/15 text-primary",
          )}
        >
          {live ? "Conto reale · denaro vero" : "Conto demo · nessun denaro reale"}
        </div>
        <div className="space-y-4 px-4 py-4">
          <h2 id={`ordine-${ideaId}`} className="text-base font-semibold">
            Conferma ordine di acquisto
          </h2>

          {phase.kind === "loading" && (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 aria-hidden className="size-4 animate-spin" /> Controllo limiti e prezzo…
            </p>
          )}

          {(phase.kind === "preview" || phase.kind === "sending") && (
            <>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 rounded-sm border bg-background/40 px-3 py-3 text-sm">
                <dt className="text-muted-foreground">Strumento</dt>
                <dd className="text-right">
                  {phase.data.name}
                  <span className="num block text-2xs text-subtle">{phase.data.ticker}</span>
                </dd>
                <dt className="text-muted-foreground">Quantità</dt>
                <dd className="num text-right">{formatNumber(phase.data.quantity, 2)}</dd>
                <dt className="text-muted-foreground">Prezzo indicativo</dt>
                <dd className="num text-right">
                  {formatPrice(phase.data.price)} {phase.data.currency}
                </dd>
                <dt className="text-muted-foreground">Importo stimato</dt>
                <dd className="num text-right font-medium">{formatEur(phase.data.estimated_eur)}</dd>
                <dt className="text-muted-foreground">Stop di protezione</dt>
                <dd className="num text-right text-down">
                  −{formatNumber(phase.data.stop_pct * 100, 1)}%
                  <span className="block text-2xs text-subtle">
                    circa {formatPrice(phase.data.stop_price)} {phase.data.currency}
                  </span>
                </dd>
                <dt className="text-muted-foreground">Perdita massima stimata</dt>
                <dd className="num text-right">{formatEur(phase.data.risk_eur)}</dd>
              </dl>
              <p className="text-2xs leading-relaxed text-muted-foreground">
                Ordine a mercato: il prezzo finale può differire. Lo stop si calcola sul prezzo di esecuzione. Limite
                per ordine {formatEur(phase.data.max_order_eur)}. Strumento informativo, non consulenza.
              </p>
            </>
          )}

          {phase.kind === "done" && (
            <div className="space-y-2 text-sm" role="status">
              <p className={cn("font-medium", phase.order.status === "eseguito" ? "text-up" : "text-warn")}>
                {STATUS_TEXT[phase.order.status]}
              </p>
              {phase.order.stop_status === "attivo" && phase.order.stop_price != null && (
                <p className="num text-xs text-muted-foreground">
                  Stop attivo a {formatPrice(phase.order.stop_price)}
                </p>
              )}
              {phase.order.error && (
                <p className="flex items-start gap-1.5 text-xs text-warn">
                  <AlertTriangle aria-hidden className="mt-px size-3.5 shrink-0" />
                  {phase.order.error}
                </p>
              )}
            </div>
          )}

          {phase.kind === "error" && (
            <p role="alert" className="flex items-start gap-1.5 text-sm text-warn">
              <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />
              {phase.message}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={close}
              disabled={phase.kind === "sending"}
              className="h-9 rounded-sm px-3 text-sm text-muted-foreground hover:text-foreground disabled:opacity-50"
            >
              {phase.kind === "done" || phase.kind === "error" ? "Chiudi" : "Annulla"}
            </button>
            {(phase.kind === "preview" || phase.kind === "sending") && (
              <button
                type="button"
                autoFocus={false}
                disabled={phase.kind === "sending" || secondsLeft === 0}
                onClick={() => phase.kind === "preview" && confirm(phase.data)}
                className={cn(
                  "num inline-flex h-9 items-center gap-2 rounded-sm px-4 text-sm font-medium transition-colors disabled:opacity-50",
                  live ? "bg-warn text-background hover:bg-warn/85" : "bg-primary text-primary-foreground hover:bg-primary/85",
                )}
              >
                {phase.kind === "sending" ? (
                  <>
                    <Loader2 aria-hidden className="size-4 animate-spin" /> Invio…
                  </>
                ) : secondsLeft === 0 ? (
                  "Scaduta: riapri"
                ) : (
                  `Conferma ordine · ${secondsLeft}s`
                )}
              </button>
            )}
          </div>
        </div>
      </dialog>
    </>
  );
}
