"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { cn } from "@/lib/utils";

/** Blocco totale: attivarlo è immediato, disattivarlo chiede conferma. */
export function KillSwitch({ active, canDisable }: { active: boolean; canDisable: boolean }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const toggle = (next: boolean) => {
    if (!next && !window.confirm("Riattivare gli ordini? Ogni ordine richiederà comunque la tua conferma.")) return;
    setError(null);
    startTransition(async () => {
      const response = await fetch("/api/ordini/blocco", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ active: next }),
      }).catch(() => null);
      if (!response?.ok) {
        const data = (await response?.json().catch(() => ({}))) as { detail?: string } | undefined;
        setError(data?.detail ?? "Operazione non riuscita");
        return;
      }
      router.refresh();
    });
  };

  return (
    <div className="flex flex-wrap items-center gap-3">
      <span
        className={cn(
          "inline-flex items-center gap-1.5 text-sm font-medium",
          active ? "text-warn" : "text-up",
        )}
      >
        <span aria-hidden className={cn("size-2 rounded-full", active ? "bg-warn" : "bg-up")} />
        {active ? "Blocco totale attivo: nessun ordine" : "Ordini abilitati con conferma"}
      </span>
      {active ? (
        <button
          type="button"
          disabled={pending || !canDisable}
          onClick={() => toggle(false)}
          className="h-8 rounded-sm border border-border-strong px-3 text-xs text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
        >
          Riattiva ordini
        </button>
      ) : (
        <button
          type="button"
          disabled={pending}
          onClick={() => toggle(true)}
          className="h-8 rounded-sm bg-down px-3 text-xs font-semibold text-white transition-colors hover:bg-down/85 disabled:opacity-50"
        >
          Blocco totale
        </button>
      )}
      {error && (
        <span role="alert" className="text-xs text-warn">
          {error}
        </span>
      )}
    </div>
  );
}
