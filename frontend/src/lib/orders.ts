/** Validazione delle richieste di ordine dal browser (pura, testabile). */

export type OrderAction = "anteprima" | "invia" | "blocco";

export const TOKEN_PATTERN = /^\d+\.[0-9a-f]{64}$/;

/** Solo richieste dallo stesso sito, in JSON: un form esterno non può inviare ordini. */
export function sameOriginJson(request: Request): boolean {
  const origin = request.headers.get("origin");
  const type = request.headers.get("content-type") ?? "";
  return origin === new URL(request.url).origin && type.startsWith("application/json");
}

function positiveInt(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value > 0 && value < 2 ** 31;
}

/** Corpo già validato da inoltrare al backend, oppure null se non valido. */
export function validateOrderBody(action: OrderAction, body: unknown): Record<string, unknown> | null {
  if (typeof body !== "object" || body === null) return null;
  const b = body as Record<string, unknown>;
  if (action === "blocco") {
    return typeof b.active === "boolean" ? { active: b.active } : null;
  }
  if (!positiveInt(b.idea_id)) return null;
  if (action === "anteprima") return { idea_id: b.idea_id };
  const valid =
    typeof b.quantity === "number" &&
    Number.isFinite(b.quantity) &&
    b.quantity > 0 &&
    b.quantity <= 1_000_000 &&
    typeof b.token === "string" &&
    TOKEN_PATTERN.test(b.token);
  return valid ? { idea_id: b.idea_id, quantity: b.quantity, token: b.token } : null;
}

export const BACKEND_PATH: Record<OrderAction, string> = {
  anteprima: "/api/orders/preview",
  invia: "/api/orders",
  blocco: "/api/controls/kill-switch",
};
