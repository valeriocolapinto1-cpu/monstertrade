import { proxySymbolGet } from "@/lib/proxy";

/** Proxy verso il backend: il browser non conosce l'indirizzo dell'API. */
export async function GET(request: Request, ctx: RouteContext<"/api/candles/[symbol]">) {
  const { symbol } = await ctx.params;
  return proxySymbolGet(request, symbol, "candles");
}
