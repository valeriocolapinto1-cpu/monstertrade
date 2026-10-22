"use client";

import { RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

interface Status {
  configured: boolean;
  status: "in_corso" | "completato" | "fallito" | "sconosciuto";
  started_at: string | null;
  finished_at: string | null;
}

async function fetchStatus(): Promise<Status | null> {
  const res = await fetch("/api/aggiorna", { cache: "no-store" }).catch(() => null);
  return res?.ok ? ((await res.json()) as Status) : null;
}

const time = new Intl.DateTimeFormat("it-IT", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Rome" });

/** Avvia l'aggiornamento di prezzi, segnali e proposte e ricarica la pagina quando finisce. */
export function RefreshButton() {
  const router = useRouter();
  const [status, setStatus] = useState<Status | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const wasRunning = useRef(false);

  const apply = useCallback(
    (data: Status | null) => {
      if (!data) return;
      if (wasRunning.current && data.status !== "in_corso") {
        setMessage(data.status === "completato" ? "Proposte aggiornate" : "Aggiornamento non riuscito");
        router.refresh();
      }
      wasRunning.current = data.status === "in_corso";
      setStatus(data);
    },
    [router],
  );

  useEffect(() => {
    void fetchStatus().then(apply);
  }, [apply]);

  useEffect(() => {
    if (status?.status !== "in_corso") return;
    const timer = setInterval(() => void fetchStatus().then(apply), 15_000);
    return () => clearInterval(timer);
  }, [status?.status, apply]);

  const start = async () => {
    setMessage(null);
    const res = await fetch("/api/aggiorna", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: "{}",
    }).catch(() => null);
    const data = (await res?.json().catch(() => null)) as { detail?: string } | null;
    setMessage(data?.detail ?? "Richiesta non riuscita");
    if (res?.ok) {
      wasRunning.current = true;
      setStatus((s) => (s ? { ...s, status: "in_corso" } : s));
      setTimeout(() => void fetchStatus().then(apply), 5_000);
    }
  };

  const running = status?.status === "in_corso";
  const last = status?.finished_at ? `ultimo aggiornamento ${time.format(new Date(status.finished_at))}` : null;

  return (
    <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1 text-xs">
      <span className="text-muted-foreground" role="status">
        {message ?? (running ? "Aggiornamento in corso…" : status?.status === "fallito" ? "Ultimo aggiornamento non riuscito" : last)}
      </span>
      <button
        type="button"
        onClick={start}
        disabled={running}
        className="inline-flex h-8 items-center gap-1.5 rounded-sm border border-border-strong px-3 text-xs font-medium text-foreground transition-colors hover:bg-surface-hover disabled:opacity-60"
      >
        <RefreshCw aria-hidden className={cn("size-3.5", running && "animate-spin")} />
        {running ? "In corso" : "Aggiorna proposte"}
      </button>
    </div>
  );
}
