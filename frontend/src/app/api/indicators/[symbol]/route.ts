import { proxySymbolGet } from "@/lib/proxy";

export async function GET(request: Request, ctx: RouteContext<"/api/indicators/[symbol]">) {
  const { symbol } = await ctx.params;
  return proxySymbolGet(request, symbol, "indicators");
}
