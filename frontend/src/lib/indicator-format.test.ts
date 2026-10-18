import { describe, expect, it } from "vitest";

import { formatIndicator, seriesLabel } from "./indicator-format";
import { INDICATORS } from "./indicator-cards";

describe("indicatori", () => {
  it("formati per tipo", () => {
    expect(formatIndicator("rsi_14", 70.456)).toBe("70,5");
    expect(formatIndicator("atr_pct", 1.234)).toBe("1,23%");
    expect(formatIndicator("sma_200", 7659.4)).toBe("7.659,40");
    expect(formatIndicator("macd", null)).toBe("—");
    expect(seriesLabel("sma_200")).toBe("SMA 200");
    expect(seriesLabel("plus_di")).toBe("+DI");
  });

  it("ogni scheda ha le tre righe compilate", () => {
    for (const card of INDICATORS) {
      expect(card.measures.length).toBeGreaterThan(20);
      expect(card.reading.length).toBeGreaterThan(20);
      expect(card.misleads.length).toBeGreaterThan(20);
    }
  });
});
