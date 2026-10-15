import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Api, type Activity, type Deal, type Group, type Stats } from "../lib/api";
import { DEAL_TYPE, SEV_COLOR, SEV_ORDER, fmtDate, fmtDay, fmtValue, riskTone, shortName } from "../lib/format";
import { ClassBadge, Empty, ErrorBox, Kpi, StatusPill } from "../components/ui";

function GroupPanel({ title, g, deals, note, real }: { title: string; g: Group; deals: Deal[]; defs: Record<string, string>; note?: string; real?: boolean }) {
  const nav = useNavigate();
  const risk = deals.filter(d => d.risk_score != null).map(d => ({ id: d.id, name: shortName(d.name), score: d.risk_score! }));
  const src = g.sources ?? {};
  const gapDeals = (g.deals_detail ?? []).filter(d => d.gaps.length);
  const sev = SEV_ORDER.map(s => ({ name: s, value: g.findings_by_severity[s] ?? 0 }));
  return (
    <section className="space-y-4" aria-label={title}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold text-ink-950">{title}</h2>
        {note && <p className="text-xs text-slate-500">{note}</p>}
      </div>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6" data-testid={real ? "kpis-real" : undefined}>
        <Kpi label="Companies reviewed" value={<span>{g.deals_scored}<span className="text-base text-slate-400"> / {g.deals}</span></span>} hint="With a scored analysis" />
        <Kpi label="Ready to submit" value={g.ready_to_submit ?? 0} hint="Deals whose latest version is an unsubmitted draft" />
        <Kpi label="Awaiting approval" value={g.awaiting_review} hint="Submitted; partner sign-off required" />
        <Kpi label="Approved" value={g.approved ?? 0} hint="Deals with an approved version (may be older than the latest draft)" />
        <Kpi label="Diligence gaps" value={<span className={g.deals_with_gaps ? "text-amber-700" : ""}>{g.gap_categories ?? 0}</span>}
          hint={`Evidence categories with insufficient evidence, across ${g.deals_with_gaps ?? 0} deal(s)`} />
        {real ? <Kpi label="Reported facts confirmed in filings" value={<span>{g.facts_confirmed_in_filing}<span className="text-base text-slate-400"> / {g.reported_facts}</span></span>}
          hint={`${g.facts_composite ? `${g.facts_composite} more are sums of separately printed lines. ` : ""}Sources: ${(src.modes ?? []).map(m => m === "snapshot" ? "stored snapshots" : "live").join(", ") || "none"}${src.oldest_retrieval_days != null ? `, oldest retrieved ${src.oldest_retrieval_days} days ago` : ""}${src.stale ? `, ${src.stale} stale` : ""}`} />
          : <Kpi label="Findings accepted / rejected" value={<span>{g.findings_accepted}<span className="text-base text-slate-400"> / {g.findings_rejected}</span></span>} hint="Quality-gate outcome" />}
      </div>
      {deals.length === 0 ? <Empty>No deals in this group.</Empty> : (
        <div className="grid items-start gap-4 lg:grid-cols-3">
          <div className="card p-5 lg:col-span-2">
            <h3 className="text-sm font-semibold text-ink-900">Risk score by deal (latest scored run)</h3>
            <p className="text-[11px] text-slate-500">Screening scores of this methodology — not default probabilities or ratings. Click a bar to open the deal.</p>
            {risk.length ? <ResponsiveContainer width="100%" height={70 + risk.length * 48}>
              <BarChart data={risk} layout="vertical" margin={{ left: 10, right: 30 }}>
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v: number) => [`${v} / 100`, "Risk score"]} />
                <Bar dataKey="score" radius={[0, 4, 4, 0]} barSize={22} isAnimationActive={false} cursor="pointer"
                  onClick={(d: any) => d?.id && nav(`/deals/${d.id}`)}>
                  {risk.map(r => <Cell key={r.name} fill={r.score >= 75 ? "#e11d48" : r.score >= 55 ? "#f97316" : r.score >= 30 ? "#f59e0b" : "#10b981"} />)}
                  <LabelList dataKey="score" position="right" fontSize={11} />
                </Bar>
              </BarChart></ResponsiveContainer> : <Empty>Run an analysis to score these deals.</Empty>}
          </div>
          <div className="card p-5">
            <h3 className="text-sm font-semibold text-ink-900">Accepted findings by severity</h3>
            <ul className="mt-3 space-y-2">{sev.map(s => (
              <li key={s.name} className="flex items-center gap-3 text-sm">
                <span className="w-16 capitalize text-slate-600">{s.name}</span>
                <span className="h-2 rounded-sm" style={{ width: `${Math.min(100, s.value * 8)}%`, background: SEV_COLOR[s.name], minWidth: s.value ? 6 : 0 }} />
                <span className="tabular-nums text-slate-700">{s.value}</span></li>))}</ul>
            <h3 className="mt-5 text-sm font-semibold text-ink-900">Open diligence gaps</h3>
            {gapDeals.length === 0 ? <p className="mt-1 text-xs text-slate-500">None recorded in the latest runs.</p> :
              <ul className="mt-2 space-y-2 text-xs" data-testid={real ? "gap-list" : undefined}>{gapDeals.map(d => (
                <li key={d.deal_id}><Link to={`/deals/${d.deal_id}`} className="font-medium text-ink-900 hover:underline">{shortName(d.name)}</Link>
                  <ul className="ml-3 list-disc text-amber-800">{d.gaps.map(x => <li key={x}>{x}</li>)}</ul></li>))}</ul>}
          </div>
        </div>)}
      {deals.length > 0 && <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="px-4 py-3">Deal</th><th className="px-4 py-3">Type</th><th className="px-4 py-3">Period end</th>
              <th className="px-4 py-3 text-right">Size / exposure</th><th className="px-4 py-3">Analysis state</th><th className="px-4 py-3 text-right">Risk (latest version)</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">{deals.map(d => (
            <tr key={d.id} className="hover:bg-slate-50">
              <td className="px-4 py-3"><Link to={`/deals/${d.id}`} className="font-medium text-ink-900 hover:underline">{d.name}</Link>
                <div className="text-xs text-slate-500">{d.target_company}</div></td>
              <td className="px-4 py-3 text-slate-600">{DEAL_TYPE[d.deal_type] ?? d.deal_type}</td>
              <td className="px-4 py-3 text-slate-600">{fmtDay(d.reporting_period_end)}</td>
              <td className="px-4 py-3 text-right tabular-nums" title={d.deal_size_basis ?? "Not stated"}>
                {d.deal_size_musd != null ? fmtValue(d.deal_size_musd, "USD_millions") : <span className="text-slate-400">not stated</span>}</td>
              <td className="px-4 py-3" data-testid={`deal-state-${d.id}`}>{d.latest_version != null ? <>
                <StatusPill s={d.latest_status ?? d.status} /><div className="mt-1 text-[11px] text-slate-500">latest v{d.latest_version}
                  {d.approved_version != null ? ` · approved v${d.approved_version}${d.approved_version !== d.latest_version ? ` (${d.approved_risk_score}/100)` : ""}` : " · none approved"}</div></>
                : <StatusPill s={d.status} />}</td>
              <td className={`px-4 py-3 text-right font-semibold tabular-nums ${riskTone(d.risk_score)}`}>{d.risk_score ?? "—"}</td>
            </tr>))}</tbody>
        </table>
        <p className="px-4 py-2 text-xs text-slate-500">{g.exposure_note}. Hover a value to see its basis.</p>
      </div>}
    </section>
  );
}

function ActivityPanel({ items }: { items: Activity[] }) {
  return (
    <section className="card p-5" aria-label="Recent activity" data-testid="activity">
      <h2 className="text-sm font-semibold text-ink-900">Recent analysis and approval activity</h2>
      {items.length === 0 ? <p className="mt-2 text-xs text-slate-500">No activity yet.</p> :
        <ol className="mt-3 divide-y divide-slate-100 text-sm">{items.map((a, i) => (
          <li key={i} className="flex flex-wrap items-baseline justify-between gap-2 py-2">
            <span><Link to={`/deals/${a.deal_id}`} className="font-medium text-ink-900 hover:underline">{shortName(a.deal)}</Link>
              <span className="text-slate-600"> · v{a.version} {a.action}</span>{a.by && <span className="text-slate-500"> by {a.by}</span>}
              {a.detail && <span className="text-slate-500"> — {a.action.startsWith("analysis") ? a.detail : `“${a.detail}”`}</span>}</span>
            <time className="text-xs tabular-nums text-slate-400">{fmtDate(a.at)}</time></li>))}</ol>}
    </section>);
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [acts, setActs] = useState<Activity[]>([]);
  const [err, setErr] = useState("");
  const [at, setAt] = useState<Date | null>(null);
  const load = useCallback(() => Promise.all([Api.stats(), Api.deals(), Api.activity()])
    .then(([s, d, a]) => { setStats(s); setDeals(d); setActs(a); setAt(new Date()); setErr(""); })
    .catch(e => setErr(e.message)), []);
  useEffect(() => {   // refresh when the tab regains focus and every 30 s, so the overview never shows stale run states
    load();
    const t = window.setInterval(load, 30000);
    window.addEventListener("focus", load);
    return () => { window.clearInterval(t); window.removeEventListener("focus", load); };
  }, [load]);
  if (err && !stats) return <ErrorBox>Could not load the portfolio: {err}</ErrorBox>;
  if (!stats) return <div className="text-sm text-slate-500">Loading portfolio…</div>;
  const by = (c: string) => deals.filter(d => d.data_classification === c);
  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-2xl font-semibold text-ink-950">Portfolio overview</h1>
        <p className="text-sm text-slate-500">Verified real-data deals are kept separate from illustrative demo deals; their figures are never combined.</p>
        <div className="mt-2 flex flex-wrap items-center gap-2"><ClassBadge c="verified_real" /><ClassBadge c="illustrative" /><ClassBadge c="user_supplied" />
          {at && <span className="ml-auto text-[11px] text-slate-400">updated {at.toLocaleTimeString()}{err ? " · refresh failed" : ""}</span>}</div>
      </div>
      <GroupPanel real title="Verified real-data portfolio" g={stats.verified_real} deals={by("verified_real")} defs={stats.definitions}
        note="Built only from SEC EDGAR, GLEIF and FRED retrievals; see each deal's Sources tab." />
      {by("verified_real").length >= 2 && <Link to="/compare" className="btn-ghost inline-flex" data-testid="open-compare">Compare verified companies side by side →</Link>}
      <ActivityPanel items={acts} />
      <GroupPanel title="Illustrative deals (synthetic demo data)" g={stats.illustrative} deals={by("illustrative")} defs={stats.definitions}
        note="Fictional companies with planted issues, used to demonstrate the agents." />
      {stats.user_supplied.deals > 0 && <GroupPanel title="User-supplied deals (not independently verified)" g={stats.user_supplied}
        deals={by("user_supplied")} defs={stats.definitions} />}
    </div>
  );
}
