import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { Api } from "../lib/api";
import Compare from "../pages/Compare";

const base = { period_end: "2022-12-31", status: "open", facts: [], top_findings: [], sources_mode: ["snapshot"] };

describe("company comparison", () => {
  it("names the methodology even when the first company has not been analysed, and says so", async () => {
    vi.spyOn(Api, "compare").mockResolvedValue([
      { ...base, deal_id: "o", name: "Old Dominion — FY2022", company: "OLD DOMINION FREIGHT LINE, INC.", historical_cutoff: "2023-02-22", run: null },
      { ...base, deal_id: "y", name: "Yellow — FY2022", company: "Yellow Corporation", historical_cutoff: "2023-02-09",
        run: { id: "r", version: 1, status: "completed", risk_score: 71.8, recommendation: "Renegotiate price and terms",
          methodology_version: "risk-v3/metrics-v2", breakdown: { financial: 53.1 }, coverage: [] } },
    ] as any);
    render(<MemoryRouter><Compare /></MemoryRouter>);
    expect(await screen.findByTestId("not-analysed")).toBeInTheDocument();
    expect(screen.getByTestId("compare").textContent).toContain("methodology risk-v3/metrics-v2");
    expect(screen.getByTestId("compare").textContent).not.toContain("methodology —");
  });
});
