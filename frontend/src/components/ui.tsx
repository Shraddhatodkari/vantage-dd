import { useEffect, useState, type ReactNode } from "react";
import { Api, type AiStatus } from "../lib/api";
import { BadgeCheck, CircleSlash, Eye, EyeOff, FlaskConical, ShieldCheck, UserRound } from "lucide-react";
import { CLAIM_TYPE, CLASS_LABEL, SEV_STYLE, riskTone } from "../lib/format";

export const SeverityBadge = ({ s }: { s: string }) => (
  <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase ring-1 ${SEV_STYLE[s] ?? SEV_STYLE.low}`}>{s}</span>
);

export const StatusPill = ({ s }: { s: string }) => {
  const map: Record<string, string> = {
    open: "bg-slate-100 text-slate-700", analysing: "bg-sky-100 text-sky-800", running: "bg-sky-100 text-sky-800",
    queued: "bg-slate-100 text-slate-700", in_review: "bg-violet-100 text-violet-800", awaiting_review: "bg-violet-100 text-violet-800",
    approved: "bg-brand-100 text-brand-700", rejected: "bg-rose-100 text-rose-800", rework: "bg-rose-100 text-rose-800",
    failed: "bg-rose-100 text-rose-800", incomplete: "bg-rose-100 text-rose-800",
    completed: "bg-sky-100 text-sky-800", analysed: "bg-sky-100 text-sky-800", reviewing: "bg-violet-100 text-violet-800",
  };
  const label: Record<string, string> = { completed: "draft — not submitted", analysed: "analysed — not submitted" };
  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${map[s] ?? map.open}`}>{label[s] ?? s.replace(/_/g, " ")}</span>;
};

export const ClassBadge = ({ c, historical }: { c: string; historical?: boolean }) => {
  const style = c === "verified_real" ? "bg-brand-50 text-brand-700 ring-brand-100" : c === "illustrative"
    ? "bg-amber-50 text-amber-800 ring-amber-200" : "bg-slate-100 text-slate-700 ring-slate-200";
  const Icon = c === "verified_real" ? ShieldCheck : c === "illustrative" ? FlaskConical : UserRound;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ${style}`}>
      <Icon className="h-3 w-3" aria-hidden />{CLASS_LABEL[c] ?? c}{historical ? " · historical" : ""}
    </span>);
};

export const ClaimBadge = ({ t }: { t: string }) => (
  <span className="rounded-sm bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-700">{CLAIM_TYPE[t] ?? t}</span>
);

export const VerifyBadge = ({ s }: { s: string }) =>
  s === "verified" ? <span className="inline-flex items-center gap-1 text-[11px] text-brand-700"><BadgeCheck className="h-3.5 w-3.5" />verified against source</span>
  : s === "supported" ? <span className="inline-flex items-center gap-1 text-[11px] text-sky-700"><BadgeCheck className="h-3.5 w-3.5" />interpretation, evidence verified</span>
  : <span className="inline-flex items-center gap-1 text-[11px] text-rose-700"><CircleSlash className="h-3.5 w-3.5" />rejected by quality gate</span>;

export const Kpi = ({ label, value, hint, icon }: { label: string; value: ReactNode; hint?: string; icon?: ReactNode }) => (
  <div className="card p-5">
    <div className="flex items-center justify-between text-xs font-medium uppercase tracking-wide text-slate-500">{label}{icon}</div>
    <div className="mt-2 text-3xl font-semibold text-ink-950 tabular-nums">{value}</div>
    {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
  </div>
);

export function RiskGauge({ score }: { score: number | null }) {
  const v = score ?? 0;
  const r = 52, c = Math.PI * r;
  const color = score == null ? "#cbd5e1" : v >= 75 ? "#e11d48" : v >= 55 ? "#f97316" : v >= 30 ? "#f59e0b" : "#10b981";
  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 120 70" className="w-40" role="img" aria-label={score == null ? "No risk score" : `Risk score ${v} out of 100`}>
        <path d="M8 62 A52 52 0 0 1 112 62" fill="none" stroke="#e2e8f0" strokeWidth="10" strokeLinecap="round" />
        {score != null && <path d="M8 62 A52 52 0 0 1 112 62" fill="none" stroke={color} strokeWidth="10" strokeLinecap="round" strokeDasharray={`${(v / 100) * c} ${c}`} />}
      </svg>
      <div className={`-mt-8 text-3xl font-bold tabular-nums ${riskTone(score)}`}>{score ?? "—"}</div>
      <div className="text-xs text-slate-500">{score == null ? "not scored" : "risk score / 100"}</div>
    </div>
  );
}

export const Empty = ({ children }: { children: ReactNode }) => (
  <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">{children}</div>
);

export const ErrorBox = ({ children }: { children: ReactNode }) => (
  <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{children}</div>
);

// Shown next to every AI-dependent feature: what actually runs (rules only vs a configured LLM).
export function AiModeBadge() {
  const [st, setSt] = useState<AiStatus | null>(null);
  useEffect(() => { Api.aiStatus().then(setSt).catch(() => setSt(null)); }, []);
  if (!st) return null;
  return (
    <div className={`rounded-lg px-3 py-2 text-xs ${st.mode === "rules_only" ? "bg-slate-50 text-slate-700 ring-1 ring-slate-200" : "bg-sky-50 text-sky-900 ring-1 ring-sky-200"}`}
      data-testid="ai-mode">
      <b>AI mode: {st.mode === "rules_only" ? "rules only" : `LLM configured (${st.provider}${st.model ? ` · ${st.model}` : ""})`}.</b> {st.note}
    </div>);
}

/** Masked password input with a show/hide toggle (never pre-filled, never logged). */
export function PasswordField({ id, label, value, onChange, autoComplete = "current-password" }:
  { id: string; label: string; value: string; onChange: (v: string) => void; autoComplete?: string }) {
  const [show, setShow] = useState(false);
  return (
    <div><label className="label" htmlFor={id}>{label}</label>
      <div className="relative">
        <input id={id} className="input pr-10" type={show ? "text" : "password"} autoComplete={autoComplete} value={value}
          onChange={e => onChange(e.target.value)} required />
        <button type="button" onClick={() => setShow(s => !s)} aria-label={show ? `Hide ${label}` : `Show ${label}`} aria-pressed={show}
          className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-slate-500 hover:text-slate-800">
          {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button>
      </div></div>);
}

export const PASSWORD_RULES = "At least 12 characters with upper- and lower-case letters, a digit and a symbol.";
