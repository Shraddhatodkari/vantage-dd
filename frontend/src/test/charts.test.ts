import { describe, expect, it } from "vitest";
import { SERIES, rowsFor } from "../components/charts";
import { fmtValue } from "../lib/format";

describe("display precision", () => {
  it("drops false precision on large ratios, same rule as the backend", () => {
    expect(fmtValue(2844.534, "x")).toBe("2,845x");
    expect(fmtValue(1354.2431, "x")).toBe("1,354x");
    expect(fmtValue(41.37, "x")).toBe("41.4x");
    expect(fmtValue(3.8186, "x")).toBe("3.82x");
    expect(fmtValue(-0.0408, "x")).toBe("-0.04x");
  });
});

describe("chart rows", () => {
  it("keep missing values as gaps, never zero", () => {
    const rows = rowsFor([{ metric: "revenue_growth_pct", fiscal_year: 2019, value: null },
      { metric: "revenue_growth_pct", fiscal_year: 2020, value: -2.3 }], { revenue_growth_pct: "g" });
    expect(rows).toEqual([{ year: "FY2019", g: null }, { year: "FY2020", g: -2.3 }]);
  });
});

describe("series colours", () => {
  it("has a distinct colour for each of the five verified companies", () => {
    expect(new Set(SERIES.slice(0, 5)).size).toBe(5);
  });
});
