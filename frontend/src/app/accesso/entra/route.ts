import { verifyPassword } from "@/lib/password";
import { authConfig, createSessionToken, SESSION_COOKIE, SESSION_TTL_SECONDS } from "@/lib/session";

function redirectTo(request: Request, path: string, cookie?: string): Response {
  const headers = new Headers({ Location: new URL(path, request.url).toString() });
  if (cookie) headers.append("Set-Cookie", cookie);
  return new Response(null, { status: 303, headers });
}

export async function POST(request: Request) {
  // Il form deve arrivare da questo stesso sito.
  const origin = request.headers.get("origin");
  if (origin && origin !== new URL(request.url).origin) {
    return new Response("Origine non valida", { status: 403 });
  }
  const form = await request.formData().catch(() => null);
  const password = String(form?.get("password") ?? "");
  const { enabled, secret } = authConfig();
  const hash = process.env.APP_PASSWORD_HASH ?? "";
  const ok =
    enabled && password.length > 0 && password.length <= 256 && (await verifyPassword(password, hash));
  if (!ok) {
    await new Promise((r) => setTimeout(r, 1000)); // rallenta i tentativi ripetuti
    return redirectTo(request, "/accesso?errore=1");
  }
  const token = await createSessionToken(secret, Math.floor(Date.now() / 1000));
  const secure = process.env.NODE_ENV === "production" ? "; Secure" : "";
  const cookie = `${SESSION_COOKIE}=${token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=${SESSION_TTL_SECONDS}${secure}`;
  return redirectTo(request, "/oggi", cookie);
}
