"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

/** Riparte da zero con la simulazione (utile quando cambia il capitale). */
export function ResetSimulation() {
  const router = useRouter();
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const run = () =>
    startTransition(async () => {
      setError(null);
      const response = await fetch("/api/simulazione/azzera", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: "{}",
      }).catch(() => null);
      if (!response?.ok) {
        setError("Operazione non riuscita");
        return;
      }
      setAsking(false);
      router.refresh();
    });

  return (
    <span className="flex flex-wrap items-center justify-end gap-2 text-xs normal-case tracking-normal">
      {error && (
        <span role="alert" className="text-warn">
          {error}
        </span>
      )}
      {asking ? (
        <>
          <span className="text-muted-foreground">Cancellare posizioni simulate e proposte?</span>
          <button
            type="button"
            onClick={() => setAsking(false)}
            className="rounded-sm px-2 py-1 text-muted-foreground hover:text-foreground"
          >
            No
          </button>
          <button
            type="button"
            disabled={pending}
            onClick={run}
            className="rounded-sm border border-down/60 px-2 py-1 font-medium text-down hover:bg-down-muted disabled:opacity-50"
          >
            Sì, riparti da zero
          </button>
        </>
      ) : (
        <button
          type="button"
          onClick={() => setAsking(true)}
          className="rounded-sm px-2 py-1 text-muted-foreground hover:text-foreground"
        >
          Azzera simulazione
        </button>
      )}
    </span>
  );
}
