import { apiBase, SYMBOL_PATTERN } from "@/lib/api";
import { isTimeframe } from "@/lib/instruments";

/** Proxy verso il backend: il browser non conosce l'indirizzo dell'API. */
export async function GET(request: Request, ctx: RouteContext<"/api/candles/[symbol]">) {
  const { symbol } = await ctx.params;
  const url = new URL(request.url);
  const timeframe = url.searchParams.get("timeframe") ?? "1d";
  const limit = Number(url.searchParams.get("limit") ?? "500");
  if (!SYMBOL_PATTERN.test(symbol) || !isTimeframe(timeframe)) {
    return Response.json({ detail: "Parametri non validi" }, { status: 400 });
  }
  if (!Number.isInteger(limit) || limit < 10 || limit > 5000) {
    return Response.json({ detail: "Parametri non validi" }, { status: 400 });
  }
  const query = new URLSearchParams({ timeframe, limit: String(limit) });
  try {
    const upstream = await fetch(`${apiBase()}/api/instruments/${symbol}/candles?${query}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    const body = await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: { "content-type": "application/json", "cache-control": "private, max-age=30" },
    });
  } catch {
    return Response.json({ detail: "Servizio dati non raggiungibile" }, { status: 502 });
  }
}
