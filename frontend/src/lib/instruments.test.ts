import { describe, expect, it } from "vitest";

import { isTimeframe, leverageLabel } from "./instruments";

describe("strumenti", () => {
  it("etichetta della leva", () => {
    expect(leverageLabel(1)).toBeNull();
    expect(leverageLabel(3)).toBe("3x");
    expect(leverageLabel(-3)).toBe("−3x");
  });

  it("valida i timeframe", () => {
    expect(isTimeframe("1d")).toBe(true);
    expect(isTimeframe("2h")).toBe(false);
  });
});
