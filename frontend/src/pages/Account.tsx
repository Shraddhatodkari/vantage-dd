import { useState, type FormEvent } from "react";
import { KeyRound, ShieldCheck, ShieldOff } from "lucide-react";
import { Api, type MfaSetup } from "../lib/api";
import { useAuth } from "../lib/auth";
import { PASSWORD_RULES, PasswordField } from "../components/ui";

/** Self-service account security: two-factor authentication and password change. */
export default function Account() {
  const { session } = useAuth();
  if (!session) return null;
  return (
    <div className="max-w-2xl space-y-6" data-testid="account">
      <div><h1 className="text-2xl font-semibold text-ink-950">Account security</h1>
        <p className="text-sm text-slate-500">{session.user.email} · {session.user.role}</p></div>
      {session.mfa_setup_required && <div role="alert" className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900" data-testid="mfa-required">
        Your role requires two-factor authentication. Set it up below to continue using Vantage DD.</div>}
      <TwoFactorCard />
      <PasswordCard />
    </div>);
}

const codeInput = (id: string, value: string, set: (v: string) => void) => (
  <div><label className="label" htmlFor={id}>6-digit code from your app</label>
    <input id={id} className="input max-w-40 tracking-[0.3em] tabular-nums" inputMode="numeric" autoComplete="one-time-code" maxLength={6}
      value={value} onChange={e => set(e.target.value.replace(/\D/g, ""))} required /></div>);

function TwoFactorCard() {
  const { session, setSession } = useAuth();
  const [setup, setSetup] = useState<MfaSetup | null>(null);
  const [code, setCode] = useState(""); const [pw, setPw] = useState("");
  const [msg, setMsg] = useState(""); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const enabled = !!session?.user.totp_enabled;
  const act = async (f: () => Promise<void>) => { setErr(""); setMsg(""); setBusy(true); try { await f(); } catch (x: any) { setErr(x.message); } finally { setBusy(false); } };
  const start = () => act(async () => { setSetup(await Api.mfaSetup()); setCode(""); });
  const confirm = (e: FormEvent) => { e.preventDefault(); act(async () => { setSession(await Api.mfaEnable(code)); setSetup(null); setCode(""); setMsg("Two-factor authentication is on. You will be asked for a code at every sign-in."); }); };
  const disable = (e: FormEvent) => { e.preventDefault(); act(async () => { await Api.mfaDisable(pw, code); setSession(await Api.me()); setPw(""); setCode(""); setMsg("Two-factor authentication is off."); }); };
  const qr = setup ? `data:image/svg+xml;base64,${btoa(setup.qr_svg)}` : "";
  return (
    <section className="card p-5 space-y-4" aria-label="Two-factor authentication">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 font-semibold text-ink-900"><ShieldCheck className="h-5 w-5 text-brand-600" />Two-factor authentication</h2>
        <span data-testid="mfa-status" className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${enabled ? "bg-brand-50 text-brand-700" : "bg-slate-100 text-slate-600"}`}>{enabled ? "On" : "Off"}</span>
      </div>
      <p className="text-sm text-slate-600">Sign-in asks for a 6-digit code from an authenticator app (Google Authenticator, Microsoft Authenticator, 1Password…) in addition to your password.</p>
      {!enabled && !setup && <button className="btn-brand" onClick={start} disabled={busy}><KeyRound className="h-4 w-4" />Set up two-factor authentication</button>}
      {!enabled && setup && <form onSubmit={confirm} className="space-y-3" data-testid="mfa-setup">
        <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-700">
          <li>Scan this QR code with your authenticator app, or type the key manually.</li>
          <li>Enter the 6-digit code the app shows to confirm.</li></ol>
        <div className="flex flex-wrap items-center gap-5">
          <img src={qr} alt="QR code for your authenticator app" className="h-44 w-44 rounded-lg border border-slate-200 bg-white p-1" />
          <div className="text-xs text-slate-500">Key (manual entry)<div className="mt-1 break-all font-mono text-sm text-ink-900" data-testid="mfa-secret">{setup.secret.replace(/(.{4})/g, "$1 ").trim()}</div>
            <div className="mt-1">Time-based, 6 digits, 30 seconds. Shown only now.</div></div>
        </div>
        {codeInput("mfa-code", code, setCode)}
        <div className="flex gap-2"><button className="btn-brand" disabled={busy || code.length !== 6}>Confirm and turn on</button>
          <button type="button" className="btn-ghost" onClick={() => setSetup(null)}>Cancel</button></div>
      </form>}
      {enabled && <form onSubmit={disable} className="space-y-3 border-t border-slate-100 pt-4">
        <div className="text-sm font-medium text-ink-900">Turn off</div>
        <PasswordField id="mfa-off-pw" label="Password" value={pw} onChange={setPw} />
        {codeInput("mfa-off-code", code, setCode)}
        <button className="btn-ghost" disabled={busy || !pw || code.length !== 6}><ShieldOff className="h-4 w-4" />Turn off two-factor authentication</button>
      </form>}
      {msg && <div role="status" className="rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand-700">{msg}</div>}
      {err && <div role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}
    </section>);
}

function PasswordCard() {
  const { session, setSession } = useAuth();
  const [cur, setCur] = useState(""); const [next, setNext] = useState(""); const [again, setAgain] = useState(""); const [code, setCode] = useState("");
  const [msg, setMsg] = useState(""); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const mfaOn = !!session?.user.totp_enabled;
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr(""); setMsg("");
    if (next !== again) { setErr("The new passwords do not match."); return; }
    setBusy(true);
    try { setSession(await Api.changePassword(cur, next, mfaOn ? code : undefined)); setCur(""); setNext(""); setAgain(""); setCode("");
      setMsg("Password changed. Every other session has been signed out."); }
    catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <section className="card p-5" aria-label="Change password">
      <h2 className="font-semibold text-ink-900">Change password</h2>
      <form onSubmit={submit} className="mt-3 space-y-3">
        <PasswordField id="pw-current" label="Current password" value={cur} onChange={setCur} />
        <PasswordField id="pw-new" label="New password" value={next} onChange={setNext} autoComplete="new-password" />
        <PasswordField id="pw-again" label="Repeat new password" value={again} onChange={setAgain} autoComplete="new-password" />
        <p className="text-xs text-slate-500">{PASSWORD_RULES}</p>
        {mfaOn && codeInput("pw-code", code, setCode)}
        <button className="btn-primary" disabled={busy}>Change password</button>
        {msg && <div role="status" className="rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand-700">{msg}</div>}
        {err && <div role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}
      </form>
    </section>);
}
