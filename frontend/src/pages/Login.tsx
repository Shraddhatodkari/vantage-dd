import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router";
import { Eye, EyeOff, KeyRound, LineChart, Lock, Network, Radar, ShieldCheck } from "lucide-react";
import { useAuth } from "../lib/auth";
import { Api, type PublicConfig } from "../lib/api";

export default function Login() {
  const { session, login, loginMfa } = useAuth();
  const nav = useNavigate();
  const [cfg, setCfg] = useState<PublicConfig | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState<"password" | "code">("password");
  const [code, setCode] = useState("");
  useEffect(() => { Api.meta().then(setCfg).catch(() => setCfg(null)); }, []);
  if (session) return <Navigate to={session.mfa_setup_required ? "/account" : session.user.role === "admin" ? "/audit" : "/"} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr(""); setBusy(true);
    try {
      if (step === "password") {
        const r = await login(email, password); setPassword("");
        if (r === "mfa") { setStep("code"); return; }
      } else { await loginMfa(code); }
      nav("/");
    }
    catch (x: any) {
      setErr(x.message || "Sign-in failed");
      if (step === "code" && /^Sign-in expired/.test(x.message ?? "")) { setStep("password"); setCode(""); }
    }
    finally { setBusy(false); }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="hidden lg:flex flex-col justify-between bg-ink-950 p-12 text-white">
        <div className="flex items-center gap-2"><Radar className="h-7 w-7 text-brand-500" /><span className="text-lg font-semibold">Vantage DD</span></div>
        <div>
          <h1 className="text-4xl font-semibold leading-tight">Due diligence in hours,<br />not weeks.</h1>
          <p className="mt-4 max-w-md text-slate-400">AI specialists read the data room and SEC filings, compute every ratio from reported figures, check management's claims against the evidence and draft the investment committee memo. A partner signs off on every conclusion.</p>
          <ul className="mt-8 space-y-3 text-sm text-slate-300">
            <li className="flex gap-3"><Network className="h-5 w-5 text-brand-500" />Multi-agent orchestration with LangGraph</li>
            <li className="flex gap-3"><ShieldCheck className="h-5 w-5 text-brand-500" />Every finding re-verified against its source before review</li>
            <li className="flex gap-3"><LineChart className="h-5 w-5 text-brand-500" />Real company data from SEC EDGAR, GLEIF and FRED</li>
          </ul>
        </div>
        <div className="text-xs text-slate-500">Role-based access · Partner approval · Tamper-evident audit trail</div>
      </div>
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm" aria-label="Sign in">
          <div className="lg:hidden mb-8 flex items-center gap-2"><Radar className="h-6 w-6 text-brand-600" /><span className="font-semibold">Vantage DD</span></div>
          <h2 className="text-2xl font-semibold text-ink-950">Sign in</h2>
          <p className="mt-1 text-sm text-slate-500">Use your firm credentials.</p>
          {step === "code" ? <div className="mt-8 space-y-4" data-testid="mfa-step">
            <p className="text-sm text-slate-600">Password accepted. Enter the 6-digit code from your authenticator app for <b>{email}</b>.</p>
            <div><label className="label" htmlFor="code">Authentication code</label>
              <input id="code" className="input tracking-[0.4em] text-lg tabular-nums" inputMode="numeric" autoComplete="one-time-code"
                pattern="[0-9]{6}" maxLength={6} value={code} onChange={e => setCode(e.target.value.replace(/\D/g, ""))} autoFocus required /></div>
            {err && <div role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}
            <button className="btn-primary w-full justify-center" disabled={busy || code.length !== 6}><KeyRound className="h-4 w-4" />{busy ? "Verifying…" : "Verify and sign in"}</button>
            <button type="button" className="w-full text-center text-xs text-slate-500 hover:text-slate-800" onClick={() => { setStep("password"); setCode(""); setErr(""); }}>Use a different account</button>
            <p className="text-xs text-slate-500">Lost your phone? An administrator can reset two-factor authentication for your account.</p>
          </div> :
          <div className="mt-8 space-y-4">
            <div><label className="label" htmlFor="email">Email</label>
              <input id="email" className="input" type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} required /></div>
            <div><label className="label" htmlFor="pw">Password</label>
              <div className="relative">
                <input id="pw" className="input pr-10" type={show ? "text" : "password"} autoComplete="current-password"
                  value={password} onChange={e => setPassword(e.target.value)} required />
                <button type="button" onClick={() => setShow(s => !s)} aria-label={show ? "Hide password" : "Show password"}
                  aria-pressed={show} className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-slate-500 hover:text-slate-800">
                  {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div></div>
            {err && <div role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}
            <button className="btn-primary w-full justify-center" disabled={busy}><Lock className="h-4 w-4" />{busy ? "Signing in…" : "Sign in"}</button>
            <p className="text-xs text-slate-500">Forgot your password? Ask an administrator for a one-time reset link.</p>
          </div>}
          {cfg?.demo_mode && cfg.demo_accounts.length > 0 && (
            <div className="mt-8 rounded-lg border border-amber-200 bg-amber-50 p-4" data-testid="demo-accounts">
              <div className="label text-amber-800">Demo environment</div>
              <p className="text-xs text-amber-900">Demo accounts (password is in your local <code>.env</code>, set by <code>manage.py setup</code>):</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {cfg.demo_accounts.map(d => <button type="button" key={d.email} onClick={() => setEmail(d.email)}
                  className={`rounded-full px-3 py-1 text-xs capitalize ring-1 ${email === d.email ? "bg-ink-900 text-white ring-ink-900" : "bg-white ring-amber-300 text-slate-700"}`}>{d.role}</button>)}
              </div>
            </div>)}
        </form>
      </div>
    </div>
  );
}
