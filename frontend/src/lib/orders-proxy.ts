import "server-only";

import { apiBase, apiHeaders, requireSession } from "@/lib/api";
import { BACKEND_PATH, type OrderAction, sameOriginJson, validateOrderBody } from "@/lib/orders";

/** Inoltra al backend una scrittura (ordine o blocco totale) dopo sessione, origine e validazione. */
export async function proxyOrderPost(request: Request, action: OrderAction): Promise<Response> {
  if (!sameOriginJson(request)) {
    return Response.json({ detail: "Richiesta non valida" }, { status: 403 });
  }
  await requireSession();
  const body = validateOrderBody(action, await request.json().catch(() => null));
  if (!body) return Response.json({ detail: "Dati non validi" }, { status: 400 });
  try {
    const upstream = await fetch(`${apiBase()}${BACKEND_PATH[action]}`, {
      method: "POST",
      cache: "no-store",
      headers: { ...apiHeaders(), "content-type": "application/json" },
      body: JSON.stringify(body),
      // Un ordine non si ritenta: tempo largo per attendere l'esito del broker.
      signal: AbortSignal.timeout(60_000),
    });
    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: { "content-type": "application/json", "cache-control": "no-store" },
    });
  } catch {
    const detail =
      action === "invia"
        ? "Nessuna risposta dal servizio: controlla il registro ordini prima di riprovare"
        : "Servizio non raggiungibile";
    return Response.json({ detail }, { status: 502 });
  }
}
