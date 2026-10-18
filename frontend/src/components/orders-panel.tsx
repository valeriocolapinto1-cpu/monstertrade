import { AlertTriangle } from "lucide-react";

import { KillSwitch } from "@/components/kill-switch";
import type { OrderRow, OrdersState } from "@/lib/api";
import { formatEur, formatNumber, formatPrice } from "@/lib/format";
import { cn } from "@/lib/utils";

const STATUS: Record<OrderRow["status"], { label: string; tone: string }> = {
  in_attesa: { label: "In attesa", tone: "text-muted-foreground" },
  inviato: { label: "Inviato", tone: "text-foreground" },
  eseguito: { label: "Eseguito", tone: "text-up" },
  rifiutato: { label: "Rifiutato", tone: "text-down" },
  incerto: { label: "Incerto", tone: "text-warn" },
};

const timeFmt = new Intl.DateTimeFormat("it-IT", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Europe/Rome",
});

function ModeNote({ data }: { data: OrdersState }) {
  if (data.mode === "disabled") {
    return <>Ordini disattivati sul server (ORDERS_MODE=disabled): l&apos;app propone soltanto.</>;
  }
  if (!data.configured) {
    return <>Modalità {data.mode}: manca la chiave Trading 212 con permesso di trading sul server.</>;
  }
  return (
    <>
      Modalità <strong className={data.mode === "live" ? "text-warn" : "text-primary"}>{data.mode === "live" ? "reale" : "demo"}</strong>{" "}
      · ogni ordine richiede la tua conferma · massimo {formatEur(data.limits.max_order_eur)} per ordine ·{" "}
      <span className="num">
        {data.limits.today} / {data.limits.max_orders_per_day}
      </span>{" "}
      ordini oggi
    </>
  );
}

/** Stato degli ordini, blocco totale e registro di ogni ordine inviato. */
export function OrdersPanel({ data }: { data: OrdersState | null }) {
  if (!data) {
    return (
      <p role="alert" className="rounded-md border border-warn/40 bg-warn-muted px-4 py-3 text-xs text-warn">
        Registro ordini non disponibile in questo momento.
      </p>
    );
  }
  const uncertain = data.orders.filter((o) => o.status === "incerto" || o.stop_status === "da_impostare");
  return (
    <section aria-labelledby="ordini" className="rounded-md border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <div className="space-y-1">
          <h2 id="ordini" className="text-2xs font-medium uppercase tracking-wider text-muted-foreground">
            Ordini Trading 212
          </h2>
          <p className="text-xs text-muted-foreground">
            <ModeNote data={data} />
          </p>
        </div>
        <KillSwitch active={data.kill_switch} canDisable={data.mode !== "disabled" && data.configured} />
      </div>
      {uncertain.length > 0 && (
        <p role="alert" className="flex items-start gap-2 border-b border-warn/30 bg-warn-muted px-4 py-2.5 text-xs text-warn">
          <AlertTriangle aria-hidden className="mt-px size-3.5 shrink-0" />
          {uncertain.length === 1 ? "Un ordine richiede" : `${uncertain.length} ordini richiedono`} un controllo
          nell&apos;app Trading 212 (esito incerto o stop non impostato).
        </p>
      )}
      {data.orders.length === 0 ? (
        <p className="px-4 py-6 text-center text-xs text-muted-foreground">Nessun ordine inviato finora.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr className="text-2xs uppercase tracking-wider text-subtle">
                <th scope="col" className="px-4 py-2 text-left font-medium">Data</th>
                <th scope="col" className="px-2 py-2 text-left font-medium">Strumento</th>
                <th scope="col" className="px-2 py-2 text-right font-medium">Quantità</th>
                <th scope="col" className="px-2 py-2 text-right font-medium">Importo stimato</th>
                <th scope="col" className="px-2 py-2 text-right font-medium">Eseguito a</th>
                <th scope="col" className="px-2 py-2 text-right font-medium">Stop</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Stato</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.orders.map((o) => (
                <tr key={o.id} className="align-top">
                  <td className="num px-4 py-2.5 text-xs text-muted-foreground">
                    {timeFmt.format(new Date(o.created_at))}
                    <span className={cn("ml-1.5 text-2xs uppercase", o.mode === "live" ? "text-warn" : "text-primary")}>
                      {o.mode === "live" ? "reale" : "demo"}
                    </span>
                  </td>
                  <td className="px-2 py-2.5">
                    {o.symbol}
                    <span className="num block text-2xs text-subtle">{o.ticker}</span>
                  </td>
                  <td className="num px-2 py-2.5 text-right">{formatNumber(o.quantity, 2)}</td>
                  <td className="num px-2 py-2.5 text-right">{formatEur(o.estimated_eur)}</td>
                  <td className="num px-2 py-2.5 text-right">{o.fill_price != null ? formatPrice(o.fill_price) : "—"}</td>
                  <td className="num px-2 py-2.5 text-right">
                    {o.stop_price != null ? formatPrice(o.stop_price) : "—"}
                    {o.stop_status === "da_impostare" && <span className="block text-2xs text-warn">da impostare</span>}
                  </td>
                  <td className={cn("px-4 py-2.5 text-right text-xs font-medium", STATUS[o.status].tone)}>
                    {STATUS[o.status].label}
                    {o.error && <span className="ml-auto block max-w-[16rem] text-2xs font-normal text-muted-foreground">{o.error}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
