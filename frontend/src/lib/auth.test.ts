import { describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

import { hashPassword, verifyPassword } from "./password";
import { createSessionToken, SESSION_TTL_SECONDS, verifySessionToken } from "./session";

const SECRET = "x".repeat(40);

describe("sessione", () => {
  it("firma valida e scadenza", async () => {
    const token = await createSessionToken(SECRET, 1000);
    expect(await verifySessionToken(token, SECRET, 1001)).toBe(true);
    expect(await verifySessionToken(token, SECRET, 1000 + SESSION_TTL_SECONDS + 1)).toBe(false);
  });

  it("rifiuta token alterati, segreti diversi o deboli", async () => {
    const token = await createSessionToken(SECRET, 1000);
    const [payload, sig] = token.split(".");
    const forged = `${btoa(JSON.stringify({ exp: 9e12 })).replace(/=+$/, "")}.${sig}`;
    expect(await verifySessionToken(forged, SECRET, 1001)).toBe(false);
    expect(await verifySessionToken(`${payload}.AAAA`, SECRET, 1001)).toBe(false);
    expect(await verifySessionToken(token, "y".repeat(40), 1001)).toBe(false);
    expect(await verifySessionToken(token, "corto", 1001)).toBe(false);
    expect(await verifySessionToken(undefined, SECRET, 1001)).toBe(false);
  });
});

describe("password", () => {
  it("hash scrypt verificabile", async () => {
    const hash = await hashPassword("una frase lunga e segreta");
    expect(hash.startsWith("scrypt$")).toBe(true);
    expect(await verifyPassword("una frase lunga e segreta", hash)).toBe(true);
    expect(await verifyPassword("sbagliata", hash)).toBe(false);
    expect(await verifyPassword("x", "formato$non$valido")).toBe(false);
  });
});
