import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EvidenceItem } from "../components/Evidence";
import { Api } from "../lib/api";
import { CoveragePanel, ReviewPanel } from "../pages/DealDetail";

const run: any = { id: "r1", version: 3, status: "awaiting_review" };

describe("partner review", () => {
  it("cannot reject without a reason, and sends the reason when given", async () => {
    const spy = vi.spyOn(Api, "review").mockResolvedValue({ ...run, status: "rejected" });
    const done = vi.fn();
    render(<ReviewPanel run={run} canReview startedBySelf={false} onReviewed={done} />);
    const reject = screen.getByRole("button", { name: /reject/i });
    expect(reject).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Review note"), { target: { value: "too short" } });
    expect(reject).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Review note"), { target: { value: "Refinancing evidence is missing" } });
    expect(reject).toBeEnabled();
    fireEvent.click(reject);
    await vi.waitFor(() => expect(done).toHaveBeenCalled());
    expect(spy).toHaveBeenCalledWith("r1", "rejected", "Refinancing evidence is missing");
    spy.mockRestore();
  });
});

describe("coverage panel", () => {
  it("states zero-document workstreams as a limitation", () => {
    render(<CoveragePanel coverage={[{ agent: "market_strategist", status: "completed", doc_types: ["market"], documents_reviewed: 0,
      document_names: [], facts_used: 2, rules_evaluated: 6, rule_matches: 0, candidate_findings: 0, llm: "not_configured",
      limitation: "No documents of type market in the data room — this workstream could not be performed on documents" }]} />);
    expect(screen.getByTestId("coverage-panel").textContent).toContain("0 document(s)");
    expect(screen.getByTestId("coverage-panel").textContent).toContain("could not be performed");
    expect(screen.getByTestId("coverage-panel").textContent).toContain("not a clean result");
  });
});

describe("rounding transparency", () => {
  it("shows the exact inputs behind a rounded-sm free-cash-flow figure", () => {
    render(<EvidenceItem e={{ kind: "calculation", metric: "free_cash_flow", fiscal_year: 2022, value: 916.434, display: "$916.4M",
      formula: "operating_cash_flow - capex", inputs: [{ metric: "operating_cash_flow", fiscal_year: 2022, value: 1691.582, unit: "USD_millions" },
        { metric: "capex", fiscal_year: 2022, value: 775.148, unit: "USD_millions" }] }} />);
    expect(document.body.textContent).toContain("$1,691.6M");
    expect(screen.getByTestId("exact-values").textContent).toContain("1,691.582; 775.148 → 916.434");
  });
});
