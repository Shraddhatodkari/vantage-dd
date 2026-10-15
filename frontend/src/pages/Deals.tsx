import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { Plus, X } from "lucide-react";
import { Api, type Deal } from "../lib/api";
import { DEAL_TYPE, fmtDay, fmtValue, riskTone } from "../lib/format";
import { ClassBadge, ErrorBox, StatusPill } from "../components/ui";
import { useAuth } from "../lib/auth";

export default function Deals() {
  const { can } = useAuth();
  const [deals, setDeals] = useState<Deal[]>([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", target_company: "", deal_type: "m_and_a", sector: "" });
  const [err, setErr] = useState("");
  const nav = useNavigate();
  useEffect(() => { Api.deals().then(setDeals).catch(e => setErr(e.message)); }, []);
  const create = async (e: FormEvent) => {
    e.preventDefault(); setErr("");
    try { const d = await Api.createDeal(form); nav(`/deals/${d.id}`); } catch (x: any) { setErr(x.message); }
  };
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-semibold text-ink-950">Deals</h1>
          <p className="text-sm text-slate-500">You see only the deals you are staffed on.</p></div>
        {can("deal:create") && <button className="btn-primary" onClick={() => setOpen(true)}><Plus className="h-4 w-4" />New deal</button>}
      </div>
      {err && !open && <ErrorBox>{err}</ErrorBox>}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {deals.map(d => (
          <Link key={d.id} to={`/deals/${d.id}`} className="card p-5 hover:border-slate-300 hover:shadow-sm">
            <div className="flex items-start justify-between gap-3"><div className="min-w-0">
              <div className="font-semibold text-ink-950">{d.name}</div>
              <div className="text-sm text-slate-500">{d.target_company}</div></div>
              <div className={`text-2xl font-bold tabular-nums ${riskTone(d.risk_score)}`}>{d.risk_score ?? "—"}</div></div>
            <div className="mt-3"><ClassBadge c={d.data_classification} historical={d.is_historical} /></div>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <StatusPill s={d.status} /><span>{DEAL_TYPE[d.deal_type]}</span><span>·</span><span>period end {fmtDay(d.reporting_period_end)}</span>
              <span className="ml-auto tabular-nums" title={d.deal_size_basis ?? "Not stated"}>{d.deal_size_musd != null ? fmtValue(d.deal_size_musd, "USD_millions") : "size not stated"}</span></div>
          </Link>))}
      </div>
      {open && (
        <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-label="New deal">
          <form onSubmit={create} className="card w-full max-w-md space-y-4 p-6">
            <div className="flex items-center justify-between"><h2 className="font-semibold">New deal (user-supplied documents)</h2>
              <button type="button" onClick={() => setOpen(false)} aria-label="Close"><X className="h-4 w-4" /></button></div>
            {(["name", "target_company", "sector"] as const).map(k => (
              <div key={k}><label className="label" htmlFor={k}>{k.replace("_", " ")}</label>
                <input id={k} className="input" value={form[k]} onChange={e => setForm({ ...form, [k]: e.target.value })} required minLength={2} /></div>))}
            <div><label className="label" htmlFor="type">Type</label>
              <select id="type" className="input" value={form.deal_type} onChange={e => setForm({ ...form, deal_type: e.target.value })}>
                {Object.entries(DEAL_TYPE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
            <p className="text-xs text-slate-500">Real public companies are added from SEC filings with <code>manage.py add-real-deal</code>, so their data stays verified.</p>
            {err && <ErrorBox>{err}</ErrorBox>}
            <button className="btn-primary w-full justify-center">Create deal</button>
          </form>
        </div>)}
    </div>
  );
}
