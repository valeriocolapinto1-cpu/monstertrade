import { proxyOrderPost } from "@/lib/orders-proxy";

export async function POST(request: Request) {
  return proxyOrderPost(request, "azzera-simulazione");
}
