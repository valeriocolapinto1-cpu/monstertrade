import { requireSession } from "@/lib/api";
import { sameOriginJson } from "@/lib/orders";
import { refreshStatus, triggerRefresh } from "@/lib/refresh";

export async function GET() {
  await requireSession();
  return Response.json(await refreshStatus(), { headers: { "cache-control": "no-store" } });
}

export async function POST(request: Request) {
  if (!sameOriginJson(request)) return Response.json({ detail: "Richiesta non valida" }, { status: 403 });
  await requireSession();
  const result = await triggerRefresh();
  return Response.json(result, { status: result.ok ? 202 : 503 });
}
