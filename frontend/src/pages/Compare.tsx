import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { Api, type CompareRow } from "../lib/api";
import { CATEGORY_LABEL, METRIC_LABEL, fmtDay, fmtValue, riskTone, shortName } from "../lib/format";
import { Empty, ErrorBox, SeverityBadge, StatusPill } from "../components/ui";
import { TrendChart } from "../components/charts";

const TABLE_METRICS = ["revenue", "revenue_growth_pct", "ebitda", "ebitda_margin_pct", "net_income", "total_debt", "cash", "net_debt",
  "gross_leverage_x", "net_leverage_x", "interest_coverage_x", "operating_cash_flow", "capex", "free_cash_flow", "current_ratio_x", "dso_days"];
const UNIT: Record<string, string> = { revenue_growth_pct: "pct", ebitda_margin_pct: "pct", net_leverage_x: "x", gross_leverage_x: "x", interest_coverage_x: "x",
  current_ratio_x: "x", dso_days: "days" };
const STATUS_TEXT: Record<string, string> = { risk_found: "finding(s) raised", reviewed_no_risk: "reviewed — no rule triggered",
  insufficient_evidence: "insufficient evidence", not_performed: "not performed" };

export default function Compare() {
  const [rows, setRows] = useState<CompareRow[] | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { Api.compare().then(setRows).catch(e => setErr(e.message)); }, []);
  const years = useMemo(() => [...new Set((rows ?? []).flatMap(r => r.facts.map(f => f.fiscal_year)))].sort(), [rows]);
  if (err) return <ErrorBox>{err}</ErrorBox>;
  if (!rows) return <div className="text-sm text-slate-500">Loading comparison…</div>;
  if (rows.length < 2) return <Empty>Comparison needs at least two verified real-data deals you are staffed on.</Empty>;
  const v = (r: CompareRow, m: string, y: number) => r.facts.find(f => f.metric === m && f.fiscal_year === y)?.value ?? null;
  // each company shows its own four fiscal years (cut-offs differ: e.g. Party City is FY2018–FY2021)
  const own = (r: CompareRow) => [...new Set(r.facts.map(f => f.fiscal_year))].sort();
  const series = rows.map((r, i) => ({ key: `s${i}`, label: shortName(r.company === r.company.toUpperCase() ? r.name : r.company) }));
  const chart = (m: string) => years.map(y => ({ year: `FY${y}`, ...Object.fromEntries(rows.map((r, i) => [`s${i}`, v(r, m, y)])) }));
  return (
    <div className="space-y-6" data-testid="compare">
      <div>
        <h1 className="text-2xl font-semibold text-ink-950">Company comparison — verified historical cases</h1>
        <p className="text-sm text-slate-500">Reported and calculated figures from SEC filings (stored snapshots), each as of its own historical cut-off.
          Scores are screening outputs of methodology {[...new Set(rows.map(r => r.run?.methodology_version).filter(Boolean))].join(", ") || "(no analysis run yet)"}; they are not guarantees, ratings or calibrated default probabilities.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">{rows.map(r => (
        <div key={r.deal_id} className="card p-5">
          <div className="flex items-start justify-between gap-3">
            <div><Link to={`/deals/${r.deal_id}`} className="font-semibold text-ink-950 hover:underline">{r.company}</Link>
              <div className="text-xs text-slate-500">Period end {fmtDay(r.period_end)} · cut-off {fmtDay(r.historical_cutoff)} · sources: {r.sources_mode.map(m => m === "snapshot" ? "stored snapshot" : "live").join(", ")}</div></div>
            <div className="text-right"><div className={`text-3xl font-bold tabular-nums ${riskTone(r.run?.risk_score ?? null)}`}>{r.run?.risk_score ?? "—"}</div>
              <div className="text-xs text-slate-500">{r.run?.recommendation ?? "not scored"}</div></div>
          </div>
          {r.run && <div className="mt-2 flex items-center gap-2 text-xs text-slate-500"><StatusPill s={r.run.status} />latest analysis v{r.run.version}
            {" · "}{r.approved_version != null ? `last approved v${r.approved_version}` : "no approved version"}</div>}
          {r.run && <dl className="mt-3 grid grid-cols-2 gap-y-1 text-xs">{Object.entries(r.run.breakdown).sort((a, b) => b[1] - a[1]).flatMap(([k, p]) =>
            [<dt key={`${k}t`} className="text-slate-600">{CATEGORY_LABEL[k] ?? k}</dt>, <dd key={`${k}v`} className="text-right tabular-nums">{p} pts</dd>])}</dl>}
          {!r.run ? <p className="mt-3 text-sm text-slate-500" data-testid="not-analysed">No analysis has been run for this company yet — open the deal and click <b>Run AI diligence</b>. Its financial figures below are already available from the SEC filings.</p> : <>
          <div className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Key findings</div>
          <ul className="mt-1 space-y-1 text-sm">{r.top_findings.map(f => <li key={f.code} className="flex items-start gap-2"><SeverityBadge s={f.severity} /><span>{f.title}</span></li>)}</ul></>}
          {r.run && <>
            <div className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Evidence gaps</div>
            <ul className="mt-1 list-disc pl-4 text-xs text-amber-800">{r.run.coverage.flatMap(c => c.categories.filter(k => k.status === "insufficient_evidence")
              .map(k => <li key={c.agent + k.key}>{k.label}{k.required ? " (required — scored gap)" : ""}</li>))}</ul></>}
        </div>))}</div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <TrendChart testId="cmp-revenue" title="Revenue ($M)" unit="USD_millions" kind="bar" data={chart("revenue")} series={series} />
        <TrendChart title="EBITDA margin (%)" unit="pct" data={chart("ebitda_margin_pct")} series={series} note="EBITDA = operating income + D&A (unadjusted)." />
        <TrendChart title="Free cash flow ($M)" unit="USD_millions" kind="bar" data={chart("free_cash_flow")} series={series} note="Operating cash flow − capital expenditure." />
        <TrendChart title="Net leverage — net debt / EBITDA (x)" unit="x" data={chart("net_leverage_x")} series={series} note="Negative = net cash. Gross leverage (total debt / EBITDA) is in the table below." />
        <TrendChart title="EBITDA / interest (x, log scale)" unit="x" log data={chart("interest_coverage_x")} series={series}
          note="Log scale: Old Dominion's interest expense is tiny, so its coverage is hundreds of times Yellow's." />
        <TrendChart title="Revenue growth (%)" unit="pct" data={chart("revenue_growth_pct")} series={series} note="FY2019 growth needs FY2018 revenue: n/a." />
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm" data-testid="compare-table">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-4 py-2">Metric</th>
            {rows.map(r => own(r).map(y => <th key={r.deal_id + y} className="px-3 py-2 text-right">{shortName(series[rows.indexOf(r)].label)} FY{y}</th>))}</tr></thead>
          <tbody className="divide-y divide-slate-100">{TABLE_METRICS.map(m => (
            <tr key={m}><td className="px-4 py-1.5 text-slate-700">{METRIC_LABEL[m] ?? m}</td>
              {rows.map(r => own(r).map(y => { const x = v(r, m, y); return (
                <td key={r.deal_id + y} className={`px-3 py-1.5 text-right tabular-nums ${x == null ? "text-slate-400" : ""}`}>
                  {fmtValue(x, UNIT[m] ?? "USD_millions")}</td>); }))}</tr>))}</tbody>
        </table>
        <p className="px-4 py-2 text-xs text-slate-500">Same values as each deal's Financials tab (one API source). n/a = not reported or not meaningful — never zero.</p>
      </div>

      <div className="card p-5 text-sm">
        <div className="label">Coverage by evidence category</div>
        <div className="mt-2 grid gap-4 md:grid-cols-2">{rows.map(r => (
          <div key={r.deal_id}><div className="font-medium text-ink-900">{r.company}</div>
            {!r.run && <p className="text-xs text-slate-500">Not analysed yet — coverage is recorded when an analysis runs.</p>}
            <ul className="mt-1 space-y-0.5 text-xs">{(r.run?.coverage ?? []).flatMap(c => c.categories.map(k => (
              <li key={c.agent + k.key} className="flex justify-between gap-2"><span className="text-slate-600">{k.label}</span>
                <span className={k.status === "insufficient_evidence" ? "text-amber-700" : k.status === "risk_found" ? "text-ink-900" : "text-slate-500"}>{STATUS_TEXT[k.status] ?? k.status}</span></li>)))}</ul></div>))}</div>
        <p className="mt-3 text-[11px] text-slate-500">Limitations: rules were written after reading Yellow's filing (not a blind test); Old Dominion is the held-out case. Two companies are not a validation set.</p>
      </div>
    </div>
  );
}
