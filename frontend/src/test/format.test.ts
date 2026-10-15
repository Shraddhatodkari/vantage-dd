import { describe, expect, it } from "vitest";
import { fmtValue, roundHalfUp } from "../lib/format";

describe("number formatting matches the backend (half-up)", () => {
  it("rounds half up like Python's Decimal ROUND_HALF_UP", () => {
    expect(roundHalfUp(2.345, 2)).toBe(2.35);
    expect(roundHalfUp(-70.45, 1)).toBe(-70.5);
  });
  it("formats Yellow FY2022 values exactly as in the 10-K", () => {
    expect(fmtValue(5244.7, "USD_millions")).toBe("$5,244.7M");
    expect(fmtValue(-70.5, "USD_millions")).toBe("-$70.5M");
    expect(fmtValue(3.81852, "x")).toBe("3.82x");
    expect(fmtValue(null, "pct")).toBe("n/a");
  });
});
