import { type NextRequest, NextResponse } from "next/server";

import { authConfig, SESSION_COOKIE, verifySessionToken } from "@/lib/session";

/** Ogni pagina e ogni richiesta dati richiede una sessione valida. */
export async function proxy(request: NextRequest) {
  const { enabled, secret, misconfigured } = authConfig();
  if (misconfigured) {
    return new NextResponse("Accesso non configurato: imposta APP_PASSWORD_HASH e SESSION_SECRET.", {
      status: 503,
    });
  }
  if (!enabled) return NextResponse.next(); // solo in sviluppo locale
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (await verifySessionToken(token, secret, Math.floor(Date.now() / 1000))) {
    return NextResponse.next();
  }
  if (request.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.json({ detail: "Non autorizzato" }, { status: 401 });
  }
  return NextResponse.redirect(new URL("/accesso", request.url));
}

export const config = {
  matcher: [
    "/((?!accesso|_next/static|_next/image|icons/|icon.png|apple-icon.png|manifest.webmanifest|sw.js).*)",
  ],
};
