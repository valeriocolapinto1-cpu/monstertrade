import "server-only";

import { apiBase, apiHeaders, requireSession, SYMBOL_PATTERN } from "@/lib/api";
import { isTimeframe } from "@/lib/instruments";

/** Inoltra al backend una richiesta per simbolo validando timeframe e limite. */
export async function proxySymbolGet(
  request: Request,
  symbol: string,
  resource: "candles" | "indicators",
): Promise<Response> {
  const url = new URL(request.url);
  const timeframe = url.searchParams.get("timeframe") ?? "1d";
  const limit = Number(url.searchParams.get("limit") ?? "500");
  const valid =
    SYMBOL_PATTERN.test(symbol) &&
    isTimeframe(timeframe) &&
    Number.isInteger(limit) &&
    limit >= 10 &&
    limit <= 5000;
  if (!valid) return Response.json({ detail: "Parametri non validi" }, { status: 400 });
  await requireSession();
  const query = new URLSearchParams({ timeframe, limit: String(limit) });
  try {
    const upstream = await fetch(`${apiBase()}/api/instruments/${symbol}/${resource}?${query}`, {
      cache: "no-store",
      headers: apiHeaders(),
      signal: AbortSignal.timeout(20_000),
    });
    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: { "content-type": "application/json", "cache-control": "private, max-age=30" },
    });
  } catch {
    return Response.json({ detail: "Servizio dati non raggiungibile" }, { status: 502 });
  }
}
