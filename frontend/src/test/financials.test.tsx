import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EvidenceItem } from "../components/Evidence";

describe("evidence rendering", () => {
  it("shows the reported XBRL value with its filing reference", () => {
    render(<EvidenceItem e={{ kind: "reported_fact", metric: "revenue", fiscal_year: 2022, value: 5244.7, unit: "USD_millions",
      xbrl_tag: "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax", form: "10-K", accession: "0000950170-23-002332",
      filed: "2023-02-09", source_url: "https://data.sec.gov/api/xbrl/companyfacts/CIK0000716006.json" }} />);
    expect(screen.getByText("$5,244.7M")).toBeInTheDocument();
    expect(document.body.textContent).toContain("0000950170-23-002332");
  });
  it("shows a calculation with formula and inputs", () => {
    render(<EvidenceItem e={{ kind: "calculation", metric: "free_cash_flow", fiscal_year: 2022, value: -70.5, display: "-$70.5M",
      formula: "operating_cash_flow - capex", inputs: [{ metric: "operating_cash_flow", fiscal_year: 2022, value: 121.3, unit: "USD_millions" },
        { metric: "capex", fiscal_year: 2022, value: 191.8, unit: "USD_millions" }] }} />);
    expect(document.body.textContent).toContain("Operating cash flow FY2022 = $121.3M; Capital expenditure FY2022 = $191.8M");
  });
  vi.restoreAllMocks();
});
