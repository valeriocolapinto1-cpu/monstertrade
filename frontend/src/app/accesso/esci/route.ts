import { SESSION_COOKIE } from "@/lib/session";

export function POST(request: Request) {
  const headers = new Headers({ Location: new URL("/accesso", request.url).toString() });
  headers.append("Set-Cookie", `${SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0`);
  return new Response(null, { status: 303, headers });
}
