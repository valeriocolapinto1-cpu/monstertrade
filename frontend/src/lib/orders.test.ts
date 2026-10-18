import { describe, expect, it } from "vitest";

import { sameOriginJson, validateOrderBody } from "@/lib/orders";

const TOKEN = `1760000000.${"a".repeat(64)}`;

function req(headers: Record<string, string>): Request {
  return new Request("https://app.example/api/ordini/invia", { method: "POST", headers });
}

describe("sameOriginJson", () => {
  it("accetta solo JSON dallo stesso sito", () => {
    expect(sameOriginJson(req({ origin: "https://app.example", "content-type": "application/json" }))).toBe(true);
    expect(sameOriginJson(req({ origin: "https://evil.example", "content-type": "application/json" }))).toBe(false);
    expect(sameOriginJson(req({ "content-type": "application/json" }))).toBe(false);
    expect(
      sameOriginJson(req({ origin: "https://app.example", "content-type": "application/x-www-form-urlencoded" })),
    ).toBe(false);
  });
});

describe("validateOrderBody", () => {
  it("nessun invio senza codice di conferma valido", () => {
    expect(validateOrderBody("invia", { idea_id: 1, quantity: 2 })).toBeNull();
    expect(validateOrderBody("invia", { idea_id: 1, quantity: 2, token: "abc" })).toBeNull();
    expect(validateOrderBody("invia", { idea_id: 1, quantity: 2, token: TOKEN })).toEqual({
      idea_id: 1,
      quantity: 2,
      token: TOKEN,
    });
  });

  it("rifiuta valori non validi e campi estranei", () => {
    expect(validateOrderBody("invia", { idea_id: 1, quantity: -1, token: TOKEN })).toBeNull();
    expect(validateOrderBody("invia", { idea_id: 1, quantity: Number.NaN, token: TOKEN })).toBeNull();
    expect(validateOrderBody("anteprima", { idea_id: 0 })).toBeNull();
    expect(validateOrderBody("anteprima", { idea_id: "1" })).toBeNull();
    expect(validateOrderBody("anteprima", { idea_id: 3, extra: "x" })).toEqual({ idea_id: 3 });
    expect(validateOrderBody("blocco", { active: "true" })).toBeNull();
    expect(validateOrderBody("blocco", { active: false })).toEqual({ active: false });
    expect(validateOrderBody("anteprima", null)).toBeNull();
  });
});
