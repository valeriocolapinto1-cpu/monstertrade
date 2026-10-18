import { describe, expect, it } from "vitest";

import { romeOffsetSeconds, toChartTime } from "./chart-time";

describe("ora italiana sul grafico", () => {
  it("ora legale e solare", () => {
    expect(romeOffsetSeconds(Date.UTC(2026, 6, 1, 12) / 1000)).toBe(7200);
    expect(romeOffsetSeconds(Date.UTC(2026, 0, 15, 12) / 1000)).toBe(3600);
  });

  it("solo l'intraday viene spostato", () => {
    const t = Date.UTC(2026, 9, 16, 13, 30) / 1000;
    expect(toChartTime(t, true)).toBe(t + 7200);
    expect(toChartTime(t, false)).toBe(t);
  });
});
