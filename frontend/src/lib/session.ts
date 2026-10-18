/**
 * Sessione firmata (HMAC-SHA256) in un cookie httpOnly. Usa Web Crypto, quindi
 * funziona sia nel proxy sia nelle pagine server.
 */

export const SESSION_COOKIE = "mt_session";
export const SESSION_TTL_SECONDS = 7 * 24 * 3600;

const enc = new TextEncoder();

function b64url(bytes: Uint8Array): string {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromB64url(value: string): Uint8Array {
  const b64 = value.replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(b64 + "=".repeat((4 - (b64.length % 4)) % 4));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

async function hmac(secret: string, data: string): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(data)));
}

function equal(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

export async function createSessionToken(secret: string, nowSeconds: number): Promise<string> {
  const payload = b64url(enc.encode(JSON.stringify({ exp: nowSeconds + SESSION_TTL_SECONDS })));
  return `${payload}.${b64url(await hmac(secret, payload))}`;
}

export async function verifySessionToken(
  token: string | undefined,
  secret: string,
  nowSeconds: number,
): Promise<boolean> {
  if (!token || secret.length < 32) return false;
  const [payload, signature] = token.split(".");
  if (!payload || !signature) return false;
  try {
    if (!equal(await hmac(secret, payload), fromB64url(signature))) return false;
    const { exp } = JSON.parse(new TextDecoder().decode(fromB64url(payload))) as { exp?: unknown };
    return typeof exp === "number" && exp > nowSeconds;
  } catch {
    return false;
  }
}

/** Configurazione dell'accesso: in produzione è obbligatoria. */
export function authConfig(): { enabled: boolean; secret: string; misconfigured: boolean } {
  const secret = process.env.SESSION_SECRET ?? "";
  const hash = process.env.APP_PASSWORD_HASH ?? "";
  const enabled = secret.length >= 32 && hash.length > 0;
  const misconfigured = !enabled && process.env.NODE_ENV === "production";
  return { enabled, secret, misconfigured };
}
