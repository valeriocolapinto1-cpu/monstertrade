import { describe, expect, it } from "vitest";

import { formatEur, formatNumber, formatPercent, trendOf } from "./format";

const nbsp = / /g;

describe("formato italiano", () => {
  it("euro con virgola decimale e punto delle migliaia", () => {
    expect(formatEur(1234.5).replace(nbsp, " ")).toBe("1.234,50 €");
  });

  it("numeri con decimali fissi e migliaia sempre separate", () => {
    expect(formatNumber(0.1 + 0.2, 4)).toBe("0,3000");
    expect(formatNumber(5432.1)).toBe("5.432,10");
  });

  it("percentuali con segno esplicito", () => {
    expect(formatPercent(1.25).replace(nbsp, " ")).toBe("+1,25%");
    expect(formatPercent(-3).replace(nbsp, " ")).toBe("-3,00%");
    expect(formatPercent(0).replace(nbsp, " ")).toBe("0,00%");
  });

  it("direzione della variazione", () => {
    expect(trendOf(2)).toBe("up");
    expect(trendOf(-0.1)).toBe("down");
    expect(trendOf(0)).toBe("flat");
  });
});

describe("prezzi e date", () => {
  it("decimali in base al valore", async () => {
    const { formatPrice } = await import("./format");
    expect(formatPrice(7659.44)).toBe("7.659,44");
    expect(formatPrice(0.12345)).toBe("0,1235");
  });

  it("data in italiano", async () => {
    const { formatDate } = await import("./format");
    expect(formatDate("2026-10-16T00:00:00Z")).toBe("16 ott 2026");
  });
});
