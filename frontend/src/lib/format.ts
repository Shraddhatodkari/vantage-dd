export const SEV_ORDER = ["critical", "high", "medium", "low"] as const;
export const SEV_STYLE: Record<string, string> = {
  critical: "bg-rose-100 text-rose-800 ring-rose-200", high: "bg-orange-100 text-orange-800 ring-orange-200",
  medium: "bg-amber-50 text-amber-800 ring-amber-200", low: "bg-slate-100 text-slate-700 ring-slate-200",
};
export const SEV_COLOR: Record<string, string> = { critical: "#e11d48", high: "#f97316", medium: "#f59e0b", low: "#94a3b8" };
export const AGENT_LABEL: Record<string, string> = {
  supervisor: "Engagement Manager", financial_analyst: "Financial Analyst", legal_counsel: "Legal Counsel",
  market_strategist: "Market Strategist", esg_compliance: "ESG & Compliance", red_team: "Red Team",
  quality_gate: "Quality Gate", human_review: "Partner Review", report_writer: "Report Writer", orchestrator: "Orchestrator",
};
export const DEAL_TYPE: Record<string, string> = { m_and_a: "M&A", credit: "Credit review", vendor_risk: "Third-party risk" };
export const CLAIM_TYPE: Record<string, string> = {
  source_fact: "Source fact", calculation: "Calculation", interpretation: "Interpretation", assumption: "Assumption",
};
export const CLASS_LABEL: Record<string, string> = {
  verified_real: "Verified real data", illustrative: "Illustrative (synthetic)", user_supplied: "User-supplied (unverified)",
};
export const METRIC_LABEL: Record<string, string> = {
  revenue: "Revenue", revenue_growth_pct: "Revenue growth", operating_income: "Operating income",
  depreciation_amortization: "Depreciation & amortisation", ebitda: "EBITDA", ebitda_margin_pct: "EBITDA margin",
  operating_margin_pct: "Operating margin", net_income: "Net income", net_margin_pct: "Net margin",
  interest_expense: "Interest expense", interest_coverage_x: "EBITDA / interest", total_debt: "Total debt", cash: "Cash",
  net_debt: "Net debt", net_leverage_x: "Net leverage (net debt / EBITDA)",
  gross_leverage_x: "Gross leverage (total debt / EBITDA)", operating_cash_flow: "Operating cash flow", capex: "Capital expenditure",
  free_cash_flow: "Free cash flow", receivables: "Receivables", dso_days: "Days sales outstanding",
  receivables_growth_pct: "Receivables growth", current_assets: "Current assets", current_liabilities: "Current liabilities",
  current_ratio_x: "Current ratio", cash_conversion_x: "Cash conversion (OCF / NI)", cash_change_pct: "Cash change",
  cogs: "Cost of goods sold", operating_expenses: "Operating expenses", processed_volume: "Processed volume",
  chargeback_ratio_pct: "Chargeback ratio", fraud_loss_bps: "Fraud losses",
};
const DEC: Record<string, number> = { USD_millions: 1, USD_billions: 2, pct: 1, x: 2, days: 1, bps: 1 };

// Half-up rounding identical to the backend (decimal ROUND_HALF_UP) so the UI and reports agree.
export function roundHalfUp(v: number, d: number): number {
  const s = Math.pow(10, d);
  return Math.sign(v) * Math.round(Math.abs(v) * s + 1e-9) / s;
}
export function fmtValue(v: number | null | undefined, unit: string): string {
  if (v === null || v === undefined) return "n/a";
  // ratios carry fewer decimals as they grow (same rule as the backend's ratio_decimals)
  const d = unit === "x" ? (Math.abs(v) >= 100 ? 0 : Math.abs(v) >= 10 ? 1 : 2) : DEC[unit] ?? 2;
  const r = roundHalfUp(v, d);
  const n = Math.abs(r).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  if (unit === "USD_millions") return `${r < 0 ? "-" : ""}$${n}M`;
  if (unit === "USD_billions") return `${r < 0 ? "-" : ""}$${n}B`;
  const sign = r < 0 ? "-" : "";
  return sign + n + ({ pct: "%", x: "x", days: " days", bps: " bps" }[unit] ?? "");
}
export const riskTone = (s: number | null) =>
  s == null ? "text-slate-400" : s >= 75 ? "text-rose-600" : s >= 55 ? "text-orange-500" : s >= 30 ? "text-amber-600" : "text-brand-700";
export const fmtDate = (d: string) => new Date(d).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
export const fmtDay = (d: string | null) => (d ? new Date(d + "T00:00:00Z").toLocaleDateString(undefined, { dateStyle: "medium", timeZone: "UTC" }) : "n/a");
export const shortName = (n: string) => n.replace(/ — .*$/, "").replace(/ \(illustrative\)$/, "").replace(/^Project /, "");
export const CATEGORY_LABEL: Record<string, string> = {
  financial: "Financial", legal: "Legal", market: "Market", esg: "ESG", compliance: "Compliance",
  consistency: "Consistency (red team)", operational: "Operational",
};
