import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useParams } from "react-router";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle, Bot, Check, ChevronDown, Database, Download, FileText, Globe, Loader2, MessageSquare, Play, RefreshCw, Table2, Upload, X } from "lucide-react";
import { Api, type AskAnswer, type Coverage, type Deal, type Fact, type Finding, type Report, type Run } from "../lib/api";
import { useAuth } from "../lib/auth";
import { AGENT_LABEL, CATEGORY_LABEL, DEAL_TYPE, METRIC_LABEL, SEV_ORDER, fmtDate, fmtDay, fmtValue } from "../lib/format";
import { AiModeBadge, ClaimBadge, ClassBadge, Empty, ErrorBox, RiskGauge, SeverityBadge, StatusPill, VerifyBadge } from "../components/ui";
import { EvidenceItem } from "../components/Evidence";
import { TrendChart, rowsFor } from "../components/charts";

type Tab = "analysis" | "financials" | "sources" | "dataroom" | "ask" | "memo";

export default function DealDetail() {
  const { id = "" } = useParams();
  const { can, session } = useAuth();
  const [deal, setDeal] = useState<Deal | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [history, setHistory] = useState<Run[]>([]);
  const [tab, setTab] = useState<Tab>("analysis");
  const [err, setErr] = useState("");
  const timer = useRef<number>();

  const loadRun = useCallback(async (runId: string) => {
    try {
      const r = await Api.run(runId);
      setRun(r);
      if (["queued", "running"].includes(r.status)) timer.current = window.setTimeout(() => loadRun(runId), 1000);
      else { Api.deal(id).then(setDeal); Api.runs(id).then(setHistory).catch(() => undefined); }
    } catch (x: any) { setErr(x.message); }
  }, [id]);

  useEffect(() => {
    Api.deal(id).then(setDeal).catch(e => setErr(e.status === 404 ? "Deal not found or you are not staffed on it." : e.message));
    Api.runs(id).then(rs => { setHistory(rs); if (rs[0]) loadRun(rs[0].id); }).catch(() => undefined);
    return () => window.clearTimeout(timer.current);
  }, [id, loadRun]);

  const start = async () => {
    setErr("");
    try { const r = await Api.startRun(id); setTab("analysis"); loadRun(r.id); } catch (x: any) { setErr(x.message); }
  };

  if (!deal) return err ? <ErrorBox>{err}</ErrorBox> : <div className="text-sm text-slate-500">Loading deal…</div>;
  const busy = run != null && ["queued", "running"].includes(run.status);
  const tabs: [Tab, string, any][] = [["analysis", "Analysis", Bot], ["financials", "Financials", Table2],
    ["sources", deal.data_classification === "verified_real" ? "Sources & identity" : "Data provenance", Globe],
    ["dataroom", `Documents (${deal.documents?.length ?? 0})`, FileText], ["ask", "Ask the documents", MessageSquare], ["memo", "IC memo", Download]];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3"><h1 className="text-2xl font-semibold text-ink-950">{deal.name}</h1><StatusPill s={deal.status} /></div>
          <p className="text-sm text-slate-500">{deal.target_company} · {DEAL_TYPE[deal.deal_type]} · {deal.sector} · reporting period end {fmtDay(deal.reporting_period_end)} · {deal.currency}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2"><ClassBadge c={deal.data_classification} historical={deal.is_historical} />
            {deal.latest_version != null && <span className="text-xs text-slate-600" data-testid="version-state">Latest analysis v{deal.latest_version} ({(deal.latest_status ?? "").replace("_", " ")})
              {" · "}{deal.approved_version != null ? <>last approved v{deal.approved_version} ({deal.approved_risk_score}/100)</> : "no approved version"}</span>}</div>
        </div>
        {can("run:start") && <button className="btn-brand" onClick={start} disabled={busy}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}{busy ? "Agents working…" : "Run AI diligence"}</button>}
      </div>
      {deal.data_classification === "illustrative" && <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900">
        Illustrative deal: the company and all figures are fictional demo data. Nothing here describes a real business.</div>}
      {deal.is_historical && <div className="rounded-lg border border-sky-200 bg-sky-50 px-4 py-2 text-sm text-sky-900">
        Historical case: analysis uses only information filed on or before {deal.historical_cutoff ? fmtDay(deal.historical_cutoff) : "the Form 10-K filing date"} (the
        Form 10-K for the period ending {fmtDay(deal.reporting_period_end)}). Later evidence is removed by the quality gate.</div>}
      {err && <ErrorBox>{err}</ErrorBox>}

      <div className="flex gap-1 overflow-x-auto border-b border-slate-200" role="tablist">
        {tabs.map(([k, label, Icon]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={`flex shrink-0 items-center gap-2 border-b-2 px-4 py-2 text-sm ${tab === k ? "border-ink-900 font-medium text-ink-950" : "border-transparent text-slate-500 hover:text-slate-800"}`}>
            <Icon className="h-4 w-4" />{label}</button>))}
      </div>

      {tab === "analysis" && history.length > 1 && <RunHistory runs={history} current={run?.id} onPick={r => { window.clearTimeout(timer.current); loadRun(r); }} />}
      {tab === "analysis" && <Analysis run={run} canSubmit={can("run:start")}
        canReview={can("run:review") && run?.started_by !== session?.user.id && run?.submitted_by !== session?.user.id}
        startedBySelf={can("run:review") && (run?.started_by === session?.user.id || run?.submitted_by === session?.user.id)}
        onReviewed={r => { setRun(r); Api.deal(id).then(setDeal); Api.runs(id).then(setHistory).catch(() => undefined); }} />}
      {tab === "financials" && <Financials dealId={id} />}
      {tab === "sources" && <Sources deal={deal} canRefresh={can("source:refresh")} onRefreshed={() => Api.deal(id).then(setDeal)} />}
      {tab === "dataroom" && <DataRoom deal={deal} canUpload={can("document:upload")} onChange={() => Api.deal(id).then(setDeal)} />}
      {tab === "ask" && <Ask dealId={id} />}
      {tab === "memo" && <Memo run={run} deal={deal} />}
    </div>
  );
}

function Analysis({ run, canSubmit, canReview, startedBySelf, onReviewed }: { run: Run | null; canSubmit: boolean; canReview: boolean; startedBySelf: boolean; onReviewed: (r: Run) => void }) {
  const [sev, setSev] = useState("all");
  const [ctype, setCtype] = useState("all");
  const [showRejected, setShowRejected] = useState(false);
  if (!run) return <Empty>No analysis yet. Click <b>Run AI diligence</b> to dispatch the agent team.</Empty>;
  const all = run.findings ?? [];
  const accepted = all.filter(f => f.verification_status !== "rejected");
  const rejected = all.filter(f => f.verification_status === "rejected");
  const shown = accepted.filter(f => (sev === "all" || f.severity === sev) && (ctype === "all" || f.claim_type === ctype))
    .sort((a, b) => SEV_ORDER.indexOf(a.severity) - SEV_ORDER.indexOf(b.severity));
  const m = run.metrics || {};
  const breakdown: Record<string, number> = m.risk_breakdown ?? {};
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-4">
        <div className="card p-5 text-center">
          <RiskGauge score={run.risk_score} />
          {run.recommendation && <div className="mt-3 text-sm font-semibold text-ink-900">{run.recommendation}</div>}
          {run.risk_score != null && <p className="mt-1 text-[11px] text-slate-500" data-testid="score-disclaimer">A screening result over the evidence reviewed — not a guarantee,
            rating or investment advice. Risks outside the reviewed material are not assessed.</p>}
          <div className="mt-2 flex items-center justify-center gap-2"><StatusPill s={run.status} /><span className="text-xs text-slate-500">analysis v{run.version}</span></div>
          <div className="mt-2 text-[11px] text-slate-500">as of {fmtDay(run.as_of_date)} · method {run.methodology_version}</div>
        </div>
        {run.agent_errors?.length > 0 && <ErrorBox><b>Run {run.status}.</b> {run.agent_errors.map(e => `${AGENT_LABEL[e.agent] ?? e.agent}: ${e.error}`).join("; ")}. This run cannot be approved; start a new run.</ErrorBox>}
        {run.inputs_changed_since_run && run.status === "awaiting_review" && <ErrorBox>The documents or financial data changed after this run. Start a new run before review.</ErrorBox>}
        {run.status === "completed" && (canSubmit ? <SubmitPanel run={run} onSubmitted={onReviewed} />
          : <div className="card border-sky-200 bg-sky-50 p-4 text-sm text-sky-900" data-testid="draft-note">Draft analysis: the analyst has not yet submitted it for partner review.</div>)}
        {run.submitted_at && <div className="card p-4 text-sm" data-testid="submission"><div className="label">Analyst submission</div>
          Submitted {fmtDate(run.submitted_at)}{run.submission_note ? <> — “{run.submission_note}”</> : null}</div>}
        {run.status === "awaiting_review" && <ReviewPanel run={run} canReview={canReview} startedBySelf={startedBySelf} onReviewed={onReviewed} />}
        {run.reviewed_at && <div className="card p-4 text-sm"><div className="label">Partner decision</div>
          {run.status} on {fmtDate(run.reviewed_at)}{run.review_note ? <> — “{run.review_note}”</> : null}</div>}
        {Object.keys(breakdown).length > 0 && <div className="card p-5 text-sm">
          <div className="label">Score composition (points, sum = score)</div>
          <dl className="mt-2 grid grid-cols-2 gap-y-1">{Object.entries(breakdown).sort((a, b) => b[1] - a[1]).flatMap(([k, v]) =>
            [<dt key={`${k}-t`} className="text-slate-600">{CATEGORY_LABEL[k] ?? k}</dt>, <dd key={`${k}-v`} className="text-right tabular-nums">{v}</dd>])}</dl>
        </div>}
        <AiModeBadge />
        {(run.coverage?.length ?? 0) > 0 && <CoveragePanel coverage={run.coverage!} />}
        {m.n_candidates != null && <div className="card p-5 text-sm">
          <div className="label">Quality gate</div>
          <dl className="mt-2 grid grid-cols-2 gap-y-1">
            <dt className="text-slate-600">Candidate findings</dt><dd className="text-right tabular-nums">{m.n_candidates}</dd>
            <dt className="text-slate-600">Verified (fact / calculation)</dt><dd className="text-right tabular-nums">{m.n_verified}</dd>
            <dt className="text-slate-600">Supported interpretations</dt><dd className="text-right tabular-nums">{m.n_supported}</dd>
            <dt className="text-slate-600">Rejected</dt><dd className="text-right tabular-nums">{m.n_rejected}</dd>
            <dt className="text-slate-600">Total latency</dt><dd className="text-right tabular-nums">{((m.total_latency_ms ?? 0) / 1000).toFixed(1)}s</dd>
          </dl>
          <p className="mt-2 text-[11px] text-slate-500">Verified = every quote found at its location in the source, every number traced to a reported fact or a re-computed formula.</p>
        </div>}
        <div className="card p-5">
          <div className="label">Agent activity</div>
          <ol className="mt-3 space-y-3">{(run.events ?? []).map(e => (
            <li key={e.seq} className="relative border-l-2 border-slate-200 pl-4">
              <span className={`absolute left-[-5px] top-1.5 h-2 w-2 rounded-full ${e.status === "error" ? "bg-rose-500" : "bg-brand-500"}`} />
              <div className="flex justify-between text-xs"><span className="font-semibold text-ink-900">{AGENT_LABEL[e.agent] ?? e.agent}</span>
                {e.latency_ms > 0 && <span className="tabular-nums text-slate-400">{e.latency_ms} ms</span>}</div>
              <p className={`text-xs ${e.status === "error" ? "text-rose-700" : "text-slate-600"}`}>{e.message}</p>
            </li>))}
            {["queued", "running"].includes(run.status) && <li className="flex items-center gap-2 pl-4 text-xs text-slate-500"><Loader2 className="h-3 w-3 animate-spin" />agents working…</li>}
          </ol>
        </div>
      </div>
      <div className="space-y-3 lg:col-span-2">
        <div className="flex flex-wrap items-center gap-2">
          <select className="input w-auto" value={sev} onChange={e => setSev(e.target.value)} aria-label="Filter severity">
            <option value="all">All severities</option>{SEV_ORDER.map(s => <option key={s}>{s}</option>)}</select>
          <select className="input w-auto" value={ctype} onChange={e => setCtype(e.target.value)} aria-label="Filter claim type">
            <option value="all">All claim types</option><option value="source_fact">Source facts</option><option value="calculation">Calculations</option>
            <option value="interpretation">Interpretations</option></select>
          <span className="ml-auto text-xs text-slate-500">{shown.length} of {accepted.length} accepted findings</span>
        </div>
        {shown.length === 0 ? <Empty>{["queued", "running"].includes(run.status) ? "Findings appear after the quality gate." : "No accepted findings match."}</Empty>
          : shown.map(f => <FindingCard key={f.id} f={f} />)}
        {rejected.length > 0 && <div className="card p-4">
          <button className="flex w-full items-center justify-between text-sm font-medium text-ink-900" onClick={() => setShowRejected(s => !s)} aria-expanded={showRejected}>
            <span className="flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-rose-600" />{rejected.length} claim(s) rejected by the quality gate (excluded from score and memo)</span>
            <ChevronDown className={`h-4 w-4 transition ${showRejected ? "rotate-180" : ""}`} /></button>
          {showRejected && <div className="mt-3 space-y-3">{rejected.map(f => <FindingCard key={f.id} f={f} />)}</div>}
        </div>}
      </div>
    </div>
  );
}

function RunHistory({ runs, current, onPick }: { runs: Run[]; current?: string; onPick: (id: string) => void }) {
  return (
    <div className="card overflow-x-auto p-3" data-testid="run-history">
      <div className="label px-1">Analysis history</div>
      <div className="mt-2 flex gap-2">{runs.map(r => (
        <button key={r.id} onClick={() => onPick(r.id)} aria-pressed={r.id === current}
          className={`shrink-0 rounded-lg border px-3 py-1.5 text-left text-xs ${r.id === current ? "border-ink-900 bg-slate-50" : "border-slate-200 hover:border-slate-400"}`}>
          <div className="font-medium text-ink-900">v{r.version} · {r.status.replace("_", " ")}</div>
          <div className="text-slate-500">{r.risk_score != null ? `${r.risk_score}/100` : "no score"} · {fmtDate(r.created_at)}</div>
        </button>))}</div>
    </div>
  );
}

const TIME_BASIS: Record<string, string> = { historical: "Historical (before cut-off)", point_in_time_filtered: "Filtered to the cut-off",
  current_metadata: "Current metadata", after_cutoff: "After cut-off — excluded", unknown: "Unknown" };
const CAT_STATUS: Record<string, string> = { risk_found: "finding(s) raised", reviewed_no_risk: "reviewed — no rule triggered",
  insufficient_evidence: "insufficient evidence", not_performed: "not performed" };
const LLM_LABEL: Record<string, string> = { not_configured: "LLM off (rules only)", ok: "LLM used", failed: "LLM failed — rules only",
  no_documents: "no documents for LLM", not_used: "rules only", not_run: "not run" };

export function CoveragePanel({ coverage }: { coverage: Coverage[] }) {
  return (
    <div className="card p-5 text-sm" data-testid="coverage-panel">
      <div className="label">Coverage — what each workstream examined</div>
      <ul className="mt-2 space-y-2">{coverage.map(c => (
        <li key={c.agent} className="text-xs">
          <div className="flex justify-between"><span className="font-semibold text-ink-900">{AGENT_LABEL[c.agent] ?? c.agent}</span>
            <span className={c.status === "failed" ? "text-rose-700" : "text-slate-500"}>{c.status === "failed" ? "failed" : LLM_LABEL[c.llm] ?? c.llm}</span></div>
          <div className="text-slate-600">{c.documents_reviewed} document(s) · {c.facts_used} reported fact(s){c.calculated_values ? ` + ${c.calculated_values} calculated value(s)` : ""} · {c.rules_evaluated} rule(s) · {c.rule_matches} match(es) · {c.candidate_findings} finding(s)</div>
          {(c.categories?.length ?? 0) > 0 ? <ul className="mt-1 space-y-0.5">{c.categories!.map(k => (
            <li key={k.key} className="flex justify-between gap-2" title={k.basis}>
              <span className="text-slate-600">{k.label}{k.required ? " *" : ""}</span>
              <span className={k.status === "insufficient_evidence" ? "text-amber-700" : k.status === "risk_found" ? "font-medium text-ink-900" : "text-slate-500"}>
                {CAT_STATUS[k.status] ?? k.status}</span></li>))}</ul>
            : c.limitation && <div className="text-amber-700">{c.limitation}</div>}
          {c.status === "failed" && <div className="text-rose-700">{c.limitation}</div>}
        </li>))}</ul>
      <p className="mt-2 text-[11px] text-slate-500">* required evidence category — if missing it is scored as a diligence gap. Hover a category for its basis.</p>
      <p className="mt-2 text-[11px] text-slate-500">A workstream with nothing to review is a gap, not a clean result.</p>
    </div>
  );
}

function FindingCard({ f }: { f: Finding }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`card p-4 ${f.verification_status === "rejected" ? "opacity-80" : ""}`} data-testid={`finding-${f.code}`}>
      <div className="flex items-start gap-3">
        <SeverityBadge s={f.severity} />
        <div className="min-w-0 flex-1">
          <div className="font-medium text-ink-950">{f.title}</div>
          <p className="mt-1 text-sm text-slate-600">{f.detail}</p>
          {f.limitations && <p className="mt-1 text-xs italic text-slate-500">Limitation: {f.limitations}</p>}
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <ClaimBadge t={f.claim_type} /><VerifyBadge s={f.verification_status} />
            <span>· {AGENT_LABEL[f.agent] ?? f.agent}</span><span className="font-mono text-[10px]">{f.code}</span>
            {f.score_points != null && f.verification_status !== "rejected" && <span className="rounded-sm bg-slate-100 px-1.5 py-0.5 tabular-nums text-slate-700"
              title={`Weight ${f.score_weight} (severity × verification factor); points = score × weight ÷ total weight`} data-testid="score-points">+{f.score_points} pts</span>}
            <button className="ml-auto flex items-center gap-1 text-ink-700 hover:underline" onClick={() => setOpen(!open)} aria-expanded={open}>
              {f.evidence.length} evidence item{f.evidence.length === 1 ? "" : "s"}<ChevronDown className={`h-3 w-3 transition ${open ? "rotate-180" : ""}`} /></button>
          </div>
          {f.verification_status === "rejected" && <p className="mt-1 text-xs text-rose-700">Reason: {f.verification_notes.join("; ")}</p>}
          {open && <div className="mt-3 space-y-2">{f.evidence.map((e, i) => <EvidenceItem key={i} e={e} />)}</div>}
        </div>
      </div>
    </div>
  );
}

export function SubmitPanel({ run, onSubmitted }: { run: Run; onSubmitted: (r: Run) => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const blocked = run.inputs_changed_since_run;
  const go = async () => {
    setBusy(true); setErr("");
    try { onSubmitted(await Api.submit(run.id, note)); } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <div className="card border-sky-200 p-4" data-testid="submit-panel">
      <div className="label text-sky-800">Ready for analyst submission</div>
      <p className="mb-3 text-xs text-slate-500">Check the findings, coverage gaps and evidence, then submit analysis v{run.version} to a partner. Nothing is approved until a different partner signs off.</p>
      <textarea className="input h-16" placeholder="Note to the reviewing partner (optional)" value={note} onChange={e => setNote(e.target.value)} maxLength={2000} aria-label="Submission note" />
      {err && <div className="mt-2"><ErrorBox>{err}</ErrorBox></div>}
      <button className="btn-brand mt-3 w-full justify-center" disabled={busy || !!blocked} onClick={go}><Check className="h-4 w-4" />Submit for partner review</button>
    </div>
  );
}

export function ReviewPanel({ run, canReview, startedBySelf, onReviewed }: { run: Run; canReview: boolean; startedBySelf: boolean; onReviewed: (r: Run) => void }) {
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  if (!canReview) return <div className="card border-violet-200 bg-violet-50 p-4 text-sm text-violet-800">
    {startedBySelf ? "You started or submitted this run, so another partner must review it (segregation of duties)." : "Awaiting partner sign-off. Only a partner staffed on this deal can approve."}</div>;
  const reasonOk = note.trim().length >= 10;
  const act = async (d: "approved" | "rejected") => {
    if (d === "rejected" && !reasonOk) { setErr("Give the reason for rejecting (at least 10 characters) so the analyst can act on it."); return; }
    setBusy(true); setErr("");
    try { onReviewed(await Api.review(run.id, d, note)); } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <div className="card border-violet-200 p-4">
      <div className="label text-violet-700">Partner review required</div>
      <p className="mb-3 text-xs text-slate-500">Approving freezes analysis v{run.version} and generates an immutable memo from exactly these findings.</p>
      <textarea className="input h-20" placeholder="Review note — optional to approve, required to reject (what must change)" value={note}
        onChange={e => setNote(e.target.value)} maxLength={2000} aria-label="Review note" />
      {err && <div className="mt-2"><ErrorBox>{err}</ErrorBox></div>}
      <div className="mt-3 flex gap-2">
        <button className="btn-brand flex-1 justify-center" disabled={busy} onClick={() => act("approved")}><Check className="h-4 w-4" />Approve</button>
        <button className="btn-ghost flex-1 justify-center" disabled={busy || !reasonOk} title={reasonOk ? "" : "A rejection needs a reason"}
          onClick={() => act("rejected")}><X className="h-4 w-4" />Reject</button>
      </div>
    </div>
  );
}

const ROWS = ["revenue", "revenue_growth_pct", "operating_income", "depreciation_amortization", "ebitda", "ebitda_margin_pct",
  "net_income", "net_margin_pct", "interest_expense", "interest_coverage_x", "total_debt", "cash", "net_debt", "gross_leverage_x", "net_leverage_x",
  "operating_cash_flow", "capex", "free_cash_flow", "current_ratio_x", "dso_days", "cash_conversion_x", "chargeback_ratio_pct", "fraud_loss_bps"];

function Financials({ dealId }: { dealId: string }) {
  const [facts, setFacts] = useState<Fact[] | null>(null);
  const [err, setErr] = useState("");
  const [sel, setSel] = useState<Fact | null>(null);
  useEffect(() => { Api.financials(dealId).then(setFacts).catch(e => setErr(e.message)); }, [dealId]);
  const idx = useMemo(() => new Map((facts ?? []).map(f => [`${f.metric}:${f.fiscal_year}`, f])), [facts]);
  if (err) return <ErrorBox>{err}</ErrorBox>;
  if (!facts) return <div className="text-sm text-slate-500">Loading…</div>;
  if (!facts.length) return <Empty>No financial data. Upload a financial-statements CSV (or add a real company from SEC filings).</Empty>;
  const years = [...new Set(facts.map(f => f.fiscal_year))].sort();
  const pe = facts.find(f => f.period_end)?.period_end;
  const R = (m: Record<string, string>) => rowsFor(facts, m);
  return (
    <div className="space-y-4">
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="fin-charts">
      <TrendChart testId="chart-revenue" title="Revenue ($M)" unit="USD_millions" kind="bar" data={R({ revenue: "v" })} series={[{ key: "v", label: "Revenue" }]} />
      <TrendChart title="EBITDA margin and net margin (%)" unit="pct" data={R({ ebitda_margin_pct: "a", net_margin_pct: "b" })}
        series={[{ key: "a", label: "EBITDA margin" }, { key: "b", label: "Net margin" }]} note="EBITDA = operating income + D&A (unadjusted)." />
      <TrendChart title="Net income ($M)" unit="USD_millions" kind="bar" data={R({ net_income: "v" })} series={[{ key: "v", label: "Net income" }]} />
      <TrendChart title="Total debt and cash ($M)" unit="USD_millions" kind="bar" data={R({ total_debt: "a", cash: "b" })}
        series={[{ key: "a", label: "Total debt" }, { key: "b", label: "Cash" }]} />
      <TrendChart title="Operating cash flow, capex and free cash flow ($M)" unit="USD_millions" kind="bar"
        data={R({ operating_cash_flow: "a", capex: "b", free_cash_flow: "c" })}
        series={[{ key: "a", label: "Operating cash flow" }, { key: "b", label: "Capex" }, { key: "c", label: "Free cash flow" }]} />
      <TrendChart testId="chart-leverage" title="Gross and net leverage (x)" unit="x" data={R({ gross_leverage_x: "g", net_leverage_x: "n" })}
        series={[{ key: "g", label: "Gross: total debt / EBITDA" }, { key: "n", label: "Net: net debt / EBITDA" }]} note="Net is negative when cash exceeds debt." />
      <TrendChart title="EBITDA / interest (x)" unit="x" data={R({ interest_coverage_x: "v" })} series={[{ key: "v", label: "EBITDA / interest" }]} />
    </div>
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="card overflow-x-auto lg:col-span-2">
        <div className="px-4 pt-4 text-xs text-slate-500">Charts above and this table read the same values. USD millions unless stated · fiscal years ending {pe ? pe.slice(5) : "n/a"} · <b>R</b> reported by source · <b>C</b> calculated (click for formula & inputs) · reported values are checked against the text of the filing they came from (<b>?</b> = not confirmed)</div>
        <table className="mt-2 w-full text-sm" data-testid="financials-table">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-4 py-2">Metric</th>
            {years.map(y => <th key={y} className="px-3 py-2 text-right">FY{y}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-100">{ROWS.filter(m => years.some(y => idx.has(`${m}:${y}`))).map(m => (
            <tr key={m}><td className="px-4 py-1.5 text-slate-700">{METRIC_LABEL[m] ?? m}</td>
              {years.map(y => { const f = idx.get(`${m}:${y}`); return (
                <td key={y} className="px-3 py-1.5 text-right tabular-nums">
                  {f ? <button className={`hover:underline ${f.value == null ? "text-slate-400" : ""}`} onClick={() => setSel(f)} data-testid={`fact-${m}-${y}`}
                    title={f.value == null ? `${f.status}: ${f.status_reason ?? ""}` : f.kind === "reported" ? (f.xbrl_tag ?? f.source_document ?? "") : (f.formula ?? "")}>
                    {f.value == null ? "n/a" : fmtValue(f.value, f.unit)} <sup className="text-[9px] text-slate-400">{f.kind === "reported" ? "R" : "C"}</sup>{f.restated && <sup className="text-[9px] text-amber-600">!</sup>}
                    {f.kind === "reported" && f.value != null && f.document_check && f.document_check !== "matched" && <sup className="text-[9px] text-amber-600" title={f.document_check_detail ?? ""}>?</sup>}</button> : <span className="text-slate-300">—</span>}
                </td>); })}</tr>))}</tbody>
        </table>
      </div>
      <div className="card p-4 text-sm">
        <div className="label">Value provenance</div>
        {!sel ? <p className="text-slate-500">Select a value to see where it came from.</p> : (
          <div className="space-y-2">
            <div className="font-medium">{METRIC_LABEL[sel.metric] ?? sel.metric} FY{sel.fiscal_year}: {sel.value == null ? "n/a" : fmtValue(sel.value, sel.unit)}</div>
            <div className="text-xs text-slate-600">{sel.kind === "reported" ? "Reported by source" : "Calculated deterministically"} · status {sel.status}{sel.status_reason ? ` (${sel.status_reason})` : ""}</div>
            {sel.period_end && <div className="text-xs text-slate-600">Period {sel.period_start ?? ""}{sel.period_start ? " → " : ""}{sel.period_end}</div>}
            {sel.xbrl_tag && <div className="font-mono text-xs text-slate-600">{sel.xbrl_tag}<br />{sel.form} {sel.accession} · filed {sel.filed}</div>}
            {sel.source_document && <div className="text-xs text-slate-600">From uploaded file {sel.source_document}</div>}
            {sel.formula && <div className="font-mono text-xs text-slate-600">{sel.formula}</div>}
            {sel.inputs?.length > 0 && <ul className="text-xs text-slate-600" data-testid="calc-inputs">{sel.inputs.map((i, k) =>
              <li key={k}>{METRIC_LABEL[i.metric] ?? i.metric} FY{i.fiscal_year} = {i.unit ? fmtValue(i.value, i.unit) : String(i.value)}
                {typeof i.value === "number" && <span className="text-slate-400"> (exact {i.value.toLocaleString("en-US", { maximumFractionDigits: 3 })})</span>}</li>)}</ul>}
            {sel.kind === "calculated" && sel.value != null && <div className="text-xs text-slate-600">Result at full precision: {sel.value.toLocaleString("en-US", { maximumFractionDigits: 4 })}.
              <span className="text-slate-400"> Each displayed figure is rounded on its own, so rounded inputs may not add up exactly to the rounded result.</span></div>}
            {sel.kind === "reported" && sel.document_check && <div className={`text-xs ${sel.document_check === "matched" ? "text-emerald-700" : "text-amber-700"}`} data-testid="doc-check">
              Filing text check: {sel.document_check.replace("_", " ")}{sel.document_check_detail ? ` — ${sel.document_check_detail}` : ""}</div>}
            {sel.document_passage && <blockquote className="border-l-2 border-slate-300 pl-2 text-xs text-slate-700" data-testid="fact-passage">
              “{sel.document_passage}”</blockquote>}
            {sel.filing_url && <a className="text-xs text-sky-700 hover:underline" href={sel.filing_url} target="_blank" rel="noreferrer noopener"
              data-testid="filing-link">Open the {sel.form ?? "filing"} {sel.accession} on SEC EDGAR</a>}
            {sel.revision_note && <div className="text-xs text-amber-700">{sel.revision_note}</div>}
            {sel.restatement_note && <div className="text-xs text-amber-700">{sel.restatement_note}</div>}
          </div>)}
      </div>
    </div>
    </div>
  );
}

function Sources({ deal, canRefresh, onRefreshed }: { deal: Deal; canRefresh: boolean; onRefreshed: () => void }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  if (deal.data_classification !== "verified_real") return (
    <div className="card p-5 text-sm text-slate-600">
      {deal.data_classification === "illustrative" ? "This illustrative deal uses synthetic files bundled with the demo. It has no external sources." :
        "Documents in this deal were uploaded by users and have not been independently verified against an authoritative source."}
    </div>);
  const c = deal.company;
  const refresh = async () => {
    setBusy(true); setErr(""); setMsg("");
    try { const r = await Api.refreshSources(deal.id); setMsg(r.changed ? `Sources changed: ${r.documents_added} new document version(s). Run a new analysis.` : "Sources unchanged."); onRefreshed(); }
    catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="card p-5 text-sm">
        <div className="label">Company identity</div>
        <p className="mt-1 rounded-sm bg-amber-50 px-2 py-1 text-[11px] text-amber-900" data-testid="identity-current">Current metadata (tickers, GLEIF LEI, registration status) retrieved {fmtDay((deal.sources ?? []).find(s => s.source === "gleif")?.retrieved_at?.slice(0, 10) ?? null)} — not as of the {deal.historical_cutoff ? fmtDay(deal.historical_cutoff) : "historical"} cut-off, and not used in scoring.</p>
        <dl className="mt-2 space-y-1">
          <div><dt className="inline text-slate-500">Name: </dt><dd className="inline">{c?.name}</dd></div>
          <div><dt className="inline text-slate-500">SEC CIK: </dt><dd className="inline font-mono">{c?.cik}</dd></div>
          <div><dt className="inline text-slate-500">Tickers: </dt><dd className="inline">{c?.tickers?.join(", ") || "none currently listed"}</dd></div>
          <div><dt className="inline text-slate-500">Industry (SIC): </dt><dd className="inline">{c?.sic} {c?.sic_description}</dd></div>
          <div><dt className="inline text-slate-500">Incorporated: </dt><dd className="inline">{c?.state_of_incorporation ?? "n/a"}</dd></div>
          <div><dt className="inline text-slate-500">GLEIF LEI: </dt><dd className="inline font-mono">{c?.lei ?? "not verified"}</dd></div>
          {!c?.lei && c?.lei_match === "jurisdiction_mismatch" && <div className="rounded-sm bg-amber-50 p-2 text-xs text-amber-900">
            GLEIF has a record with the same legal name ({c.lei_record?.candidates?.map((k: any) => `${k.lei}, ${k.jurisdiction}`).join("; ")}),
            but SEC reports incorporation in {c.lei_record?.sec_state_of_incorporation}. Not auto-accepted — manual verification required.</div>}
          {!c?.lei && c?.lei_match && c.lei_match !== "jurisdiction_mismatch" && <div className="text-xs text-slate-500">GLEIF lookup result: {c.lei_match.replace("_", " ")}</div>}
          {c?.lei && <div><dt className="inline text-slate-500">LEI status: </dt><dd className="inline">{c.lei_status} — legal name “{c.lei_legal_name}”</dd></div>}
        </dl>
      </div>
      <div className="card overflow-x-auto lg:col-span-2">
        <div className="flex items-center justify-between px-4 pt-4"><div className="label">Retrieved sources</div>
          {canRefresh && <button className="btn-ghost" onClick={refresh} disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}Refresh from sources</button>}</div>
        {msg && <p className="px-4 text-sm text-brand-700">{msg}</p>}
        {err && <div className="px-4"><ErrorBox>{err}</ErrorBox></div>}
        <table className="mt-2 w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-4 py-2">Source</th><th className="px-4 py-2">Time basis</th><th className="px-4 py-2">Retrieved (UTC)</th><th className="px-4 py-2">How obtained</th><th className="px-4 py-2">Retrieval age</th></tr></thead>
          <tbody className="divide-y divide-slate-100">{(deal.sources ?? []).map(s => (
            <tr key={s.url}><td className="px-4 py-2"><a className="text-sky-700 hover:underline" href={s.url} target="_blank" rel="noreferrer noopener">{s.label || s.source}</a>
              {s.accession && <div className="font-mono text-[11px] text-slate-500">accession {s.accession}{s.filing_date ? ` · filed ${s.filing_date}` : ""}</div>}
              {s.notes && <div className="text-[11px] text-slate-500">{s.notes}</div>}</td>
              <td className="px-4 py-2 text-xs" data-testid="time-basis"><span className={`rounded-sm px-1.5 py-0.5 font-medium ${s.time_basis === "current_metadata" ? "bg-amber-50 text-amber-800" : s.time_basis === "after_cutoff" ? "bg-rose-50 text-rose-800" : "bg-sky-50 text-sky-800"}`}>
                {TIME_BASIS[s.time_basis ?? ""] ?? s.time_basis}</span>
                <div className="mt-0.5 text-[11px] text-slate-500">{s.used_in_scoring ? "used in the assessment" : "not used in scoring"}{s.basis_note ? ` — ${s.basis_note}` : ""}</div></td>
              <td className="px-4 py-2 text-xs">{s.retrieved_at.replace("T", " ").slice(0, 19)}</td>
              <td className="px-4 py-2 text-xs" data-testid="source-mode">{s.retrieval_mode === "snapshot" ? "Stored snapshot — not re-checked since retrieval" : "Retrieved live"}</td>
              <td className="px-4 py-2 text-xs">{s.stale ? <span className="text-amber-700">retrieved {s.age_days} days ago — refresh recommended</span> : `retrieved ${s.age_days} days ago`}{s.time_basis !== "current_metadata" && <div className="text-[11px] text-slate-400">historical document: does not go stale</div>}</td></tr>))}</tbody>
        </table>
        <p className="px-4 py-2 text-xs text-slate-500"><Database className="mr-1 inline h-3 w-3" />“Stored snapshot” means the app is reading a copy retrieved at the time shown, not fetching live. The filing date is when the company published it; retrieval age is when this app last obtained the copy.</p>
      </div>
    </div>
  );
}

function DataRoom({ deal, canUpload, onChange }: { deal: Deal; canUpload: boolean; onChange: () => void }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setBusy(true); setMsg(""); setErr("");
    try {
      for (const f of Array.from(files)) { const d = await Api.upload(deal.id, f); setMsg(`Indexed ${d.filename}: ${d.n_chunks} chunks, ${d.pii_redactions} PII redactions, ${d.injection_flags} injection flags.`); }
      onChange();
    } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  const real = deal.data_classification === "verified_real";
  return (
    <div className="space-y-4">
      {canUpload && !real && <label className="card flex cursor-pointer flex-col items-center gap-2 border-dashed p-8 text-sm text-slate-500 hover:bg-slate-50">
        {busy ? <Loader2 className="h-6 w-6 animate-spin" /> : <Upload className="h-6 w-6" />}
        <span>Choose .txt, .md, .csv or .pdf. PII is redacted and embedded instructions neutralised before indexing. CSVs are validated as financial statements.</span>
        <input type="file" multiple className="hidden" accept=".txt,.md,.csv,.pdf" onChange={e => upload(e.target.files)} />
      </label>}
      {real && <p className="text-sm text-slate-600">These documents are sections of the company's Form 10-K, retrieved from SEC EDGAR. Manual uploads are disabled for verified deals.</p>}
      {msg && <div className="text-sm text-slate-600">{msg}</div>}
      {err && <ErrorBox>{err}</ErrorBox>}
      <div className="card overflow-x-auto"><table className="w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-4 py-2">Document</th><th className="px-4 py-2">Type</th><th className="px-4 py-2 text-right">Characters</th><th className="px-4 py-2 text-right">PII redacted</th><th className="px-4 py-2">Source</th></tr></thead>
        <tbody className="divide-y divide-slate-100">{(deal.documents ?? []).map(d => (
          <tr key={d.id}><td className="px-4 py-2 font-medium">{d.title ?? d.filename}</td><td className="px-4 py-2"><span className="rounded-sm bg-slate-100 px-2 py-0.5 text-xs">{d.doc_type}</span></td>
            <td className="px-4 py-2 text-right tabular-nums">{d.n_chars.toLocaleString()}</td><td className="px-4 py-2 text-right tabular-nums">{d.pii_redactions}</td>
            <td className="px-4 py-2 text-xs">{d.source_url ? <a className="text-sky-700 hover:underline" href={d.source_url} target="_blank" rel="noreferrer noopener">SEC {d.accession}</a> : d.data_classification === "illustrative" ? "synthetic demo file" : `uploaded ${fmtDate(d.uploaded_at)}`}</td></tr>))}</tbody>
      </table></div>
    </div>
  );
}

function Ask({ dealId }: { dealId: string }) {
  const [q, setQ] = useState("");
  const [ans, setAns] = useState<AskAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const ask = async (e?: FormEvent, text = q) => {
    e?.preventDefault(); if (!text.trim()) return;
    setBusy(true); setErr("");
    try { setAns(await Api.ask(dealId, text)); } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-4">
      <AiModeBadge />
      <form onSubmit={ask} className="flex gap-2">
        <input className="input" value={q} onChange={e => setQ(e.target.value)} placeholder="Ask a question about this deal's documents…" maxLength={2000} aria-label="Question" />
        <button className="btn-primary" disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Ask"}</button>
      </form>
      <div className="flex flex-wrap gap-2">{["When does the debt mature?", "What are the financial covenants?", "Is there any pending litigation?"].map(s =>
        <button key={s} className="rounded-full bg-white px-3 py-1 text-xs ring-1 ring-slate-200 hover:bg-slate-50" onClick={() => { setQ(s); ask(undefined, s); }}>{s}</button>)}</div>
      {err && <ErrorBox>{err}</ErrorBox>}
      {ans && <div className="card p-5">
        <p className="whitespace-pre-wrap text-sm text-slate-700">{ans.answer}</p>
        <p className="mt-1 text-[11px] text-slate-500" data-testid="answer-type">{ans.answer_type === "extractive" ? "Extractive search results: passages quoted from the documents, no AI-written answer."
          : ans.answer_type === "abstained" ? "The retrieved passages do not answer this question." :
          "AI-written answer; every figure was checked against the cited passages below."}</p>
        {ans.withheld_reason && <p className="mt-1 text-[11px] text-amber-700">{ans.withheld_reason}</p>}
        <div className="mt-4 label">Passages</div>
        <div className="space-y-2">{ans.citations.map((c, i) => <div key={c.chunk_id} className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600"><b>[{i + 1}] {c.filename}</b>{c.accession ? ` (SEC ${c.accession})` : ""} — {c.quote}</div>)}</div>
      </div>}
    </div>
  );
}

function Memo({ run, deal }: { run: Run | null; deal: Deal }) {
  const [rep, setRep] = useState<Report | null>(null);
  const [err, setErr] = useState("");
  // the memo of the selected version if it is approved; otherwise the deal's last APPROVED version (clearly labelled)
  const memoRunId = run?.reports && run.reports.length > 0 ? run.id : deal.approved_run_id ?? null;
  const memoVersion = memoRunId === run?.id ? run?.version : deal.approved_version;
  useEffect(() => { setRep(null); if (memoRunId) Api.report(memoRunId).then(setRep).catch(e => setErr(e.message)); }, [memoRunId]);
  if (!memoRunId) return <Empty>The investment committee memo is generated when a partner approves an analysis.</Empty>;
  if (err) return <ErrorBox>{err}</ErrorBox>;
  if (!rep) return <div className="text-sm text-slate-500">Loading memo…</div>;
  return (
    <div className="card p-6 md:p-10">
      {run && memoRunId !== run.id && <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900" data-testid="older-memo-note">
        This is the approved memo for analysis v{memoVersion}. The analysis you are viewing (v{run.version}, {run.status.replace("_", " ")}) has no approved memo; its findings may differ.</div>}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
        <span>Report v{rep.version} of analysis v{memoVersion} · approved by {rep.approved_by} on {fmtDate(rep.approved_at)} · SHA-256 <code data-testid="report-sha">{rep.content_sha256.slice(0, 16)}…</code></span>
        <span className="flex gap-2"><a className="btn-ghost" href={Api.reportUrl(memoRunId)}><Download className="h-4 w-4" />Download .md</a>
          <a className="btn-ghost" href={Api.reportUrl(memoRunId).replace(/\.md$/, ".html")}><Download className="h-4 w-4" />Download printable .html</a></span>
      </div>
      <article className="prose-memo" data-testid="memo"><ReactMarkdown remarkPlugins={[remarkGfm]}>{rep.content_md}</ReactMarkdown></article>
    </div>
  );
}
