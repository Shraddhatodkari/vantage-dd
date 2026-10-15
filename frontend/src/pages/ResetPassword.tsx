import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { Radar } from "lucide-react";
import { Api } from "../lib/api";
import { PASSWORD_RULES, PasswordField } from "../components/ui";

/** Public page for an administrator-issued, single-use reset link: /reset-password#token=…
 *  The token travels in the URL fragment, which browsers never send to the server or in Referer headers. */
export default function ResetPassword() {
  const [token] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "");
  const [pw, setPw] = useState(""); const [again, setAgain] = useState("");
  const [err, setErr] = useState(""); const [done, setDone] = useState(false); const [busy, setBusy] = useState(false);
  useEffect(() => { if (window.location.hash) history.replaceState(null, "", window.location.pathname); }, []);   // remove token from the address bar
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr("");
    if (pw !== again) { setErr("The passwords do not match."); return; }
    setBusy(true);
    try { await Api.completeReset(token, pw); setDone(true); setPw(""); setAgain(""); }
    catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm" data-testid="reset-password">
        <div className="mb-8 flex items-center gap-2"><Radar className="h-6 w-6 text-brand-600" /><span className="font-semibold">Vantage DD</span></div>
        <h1 className="text-2xl font-semibold text-ink-950">Set a new password</h1>
        {!token ? <p className="mt-4 text-sm text-rose-700" role="alert">This link has no reset token. Ask an administrator for a new link.</p>
          : done ? <div className="mt-4 space-y-3"><p role="status" className="rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand-700">Password set. Older sessions were signed out.</p>
              <Link to="/login" className="btn-primary">Go to sign in</Link></div>
          : <form onSubmit={submit} className="mt-6 space-y-4">
              <PasswordField id="new-pw" label="New password" value={pw} onChange={setPw} autoComplete="new-password" />
              <PasswordField id="new-pw2" label="Repeat new password" value={again} onChange={setAgain} autoComplete="new-password" />
              <p className="text-xs text-slate-500">{PASSWORD_RULES} The link works once and expires after a short time.</p>
              {err && <div role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{err}</div>}
              <button className="btn-primary w-full justify-center" disabled={busy}>Set password</button>
            </form>}
      </div>
    </div>);
}
