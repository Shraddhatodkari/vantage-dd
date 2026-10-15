import { useEffect, useState } from "react";
import { KeyRound, ShieldCheck, ShieldOff, Unlock } from "lucide-react";
import { Api, type AuditEntry, type DealMeta, type User } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate } from "../lib/format";
import { AiModeBadge, ClassBadge, ErrorBox, StatusPill } from "../components/ui";

export default function Audit() {
  const [rows, setRows] = useState<AuditEntry[]>([]);
  const [deals, setDeals] = useState<DealMeta[]>([]);
  const [q, setQ] = useState("");
  const [err, setErr] = useState("");
  const [verify, setVerify] = useState<string>("");
  useEffect(() => {
    Api.audit().then(setRows).catch(e => setErr(e.message));
    Api.allDealMetadata().then(setDeals).catch(() => undefined);
  }, []);
  const check = async () => {
    try { const v = await Api.verifyAudit(); setVerify(v.valid ? `Hash chain intact (${v.entries_checked} entries checked).` : "CHAIN BROKEN — audit log has been tampered with."); }
    catch (x: any) { setVerify(x.message); }
  };
  const shown = rows.filter(r => !q || `${r.action} ${r.user_email} ${r.resource} ${r.outcome}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="space-y-8">
      <div><h1 className="text-2xl font-semibold text-ink-950">Administration</h1>
        <p className="text-sm text-slate-500">Administrators manage users and audit. They cannot approve analyses or read deal evidence unless staffed on a deal.</p></div>
      {err && <ErrorBox>{err}</ErrorBox>}
      <UsersCard />
      <AiProviderCard />
      <section>
        <h2 className="mb-2 text-sm font-semibold text-ink-900">All deals (metadata only)</h2>
        <div className="card overflow-x-auto"><table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-4 py-2">Deal</th><th className="px-4 py-2">Classification</th><th className="px-4 py-2">Status</th><th className="px-4 py-2">Created</th></tr></thead>
          <tbody className="divide-y divide-slate-100">{deals.map(d => <tr key={d.id}><td className="px-4 py-2">{d.name}</td><td className="px-4 py-2"><ClassBadge c={d.data_classification} /></td>
            <td className="px-4 py-2"><StatusPill s={d.status} /></td><td className="px-4 py-2 text-xs text-slate-500">{fmtDate(d.created_at)}</td></tr>)}</tbody></table></div>
      </section>
      <section className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div><h2 className="text-sm font-semibold text-ink-900">Audit log</h2>
            <p className="text-xs text-slate-500">Append-only and hash-chained: each entry includes the hash of the previous one.</p></div>
          <div className="flex gap-2"><input className="input max-w-xs" placeholder="Filter by action, user, resource" value={q} onChange={e => setQ(e.target.value)} aria-label="Filter audit log" />
            <button className="btn-ghost" onClick={check}><ShieldCheck className="h-4 w-4" />Verify chain</button></div>
        </div>
        {verify && <div className="rounded-lg bg-slate-50 px-3 py-2 text-sm" role="status">{verify}</div>}
        <div className="card overflow-x-auto">
          <table className="w-full text-sm" data-testid="audit-table">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr>
              <th className="px-4 py-2">Time</th><th className="px-4 py-2">User</th><th className="px-4 py-2">Action</th><th className="px-4 py-2">Outcome</th><th className="px-4 py-2">Resource</th><th className="px-4 py-2">Detail</th><th className="px-4 py-2">Hash</th></tr></thead>
            <tbody className="divide-y divide-slate-100">{shown.map(r => (
              <tr key={r.id}><td className="whitespace-nowrap px-4 py-2 text-slate-500">{fmtDate(r.created_at)}</td>
                <td className="px-4 py-2">{r.user_email ?? "—"}</td><td className="px-4 py-2"><span className="rounded-sm bg-slate-100 px-2 py-0.5 text-xs">{r.action}</span></td>
                <td className={`px-4 py-2 text-xs ${r.outcome === "success" ? "text-slate-600" : "text-rose-700"}`}>{r.outcome}</td>
                <td className="px-4 py-2 font-mono text-xs text-slate-500">{r.resource}</td>
                <td className="max-w-xs truncate px-4 py-2 font-mono text-xs text-slate-500" title={JSON.stringify(r.detail)}>{JSON.stringify(r.detail)}</td>
                <td className="px-4 py-2 font-mono text-[10px] text-slate-400">{r.hash.slice(0, 10)}</td></tr>))}</tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function AiProviderCard() {
  const [res, setRes] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try { const r = await Api.aiCheck(); setRes(r.ok ? `Provider answered in ${r.latency_ms} ms.` : r.status === "not_configured" ? "No LLM provider configured — nothing was called." : `Check failed (${r.error_type}).`); }
    catch (x: any) { setRes(x.message); } finally { setBusy(false); }
  };
  return (
    <section className="space-y-2" aria-label="AI provider">
      <h2 className="text-sm font-semibold text-ink-900">AI provider</h2>
      <AiModeBadge />
      <div className="flex items-center gap-3"><button className="btn-ghost" onClick={run} disabled={busy}>Run connectivity check</button>
        <span className="text-xs text-slate-500">Makes one minimal API call when a provider is configured (small, disclosed cost). Audited.</span></div>
      {res && <div className="rounded-lg bg-slate-50 px-3 py-2 text-sm" role="status" data-testid="ai-check">{res}</div>}
    </section>);
}

/** User administration: unlock, single-use password-reset link, reset lost 2FA. Every action is audited server-side.
 *  Destructive actions need a second click (no browser dialogs). Admins cannot reset their own password or 2FA here. */
function UsersCard() {
  const { session } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [armed, setArmed] = useState("");
  const [link, setLink] = useState<{ email: string; url: string; minutes: number } | null>(null);
  const [msg, setMsg] = useState(""); const [err, setErr] = useState("");
  const load = () => Api.users().then(setUsers).catch(e => setErr(e.message));
  useEffect(() => { load(); }, []);
  const act = async (key: string, f: () => Promise<void>) => {
    if (armed !== key) { setArmed(key); return; }
    setArmed(""); setErr(""); setMsg("");
    try { await f(); await load(); } catch (x: any) { setErr(x.message); }
  };
  return (
    <section className="space-y-2" aria-label="Users">
      <h2 className="text-sm font-semibold text-ink-900">Users</h2>
      <p className="text-xs text-slate-500">Reset links are single-use, expire after a short time and are stored only as a hash. Give the link to the user through a trusted channel; it is shown once.</p>
      {link && <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm" data-testid="reset-link">
        <div className="font-medium text-amber-900">One-time reset link for {link.email} (expires in {link.minutes} minutes, shown only now)</div>
        <div className="mt-1 flex items-center gap-2"><input readOnly className="input font-mono text-xs" value={link.url} aria-label="Reset link" onFocus={e => e.currentTarget.select()} />
          <button className="btn-ghost" onClick={() => { navigator.clipboard?.writeText(link.url).catch(() => undefined); }}>Copy</button>
          <button className="btn-ghost" onClick={() => setLink(null)}>Hide</button></div></div>}
      {msg && <div role="status" className="rounded-lg bg-slate-50 px-3 py-2 text-sm">{msg}</div>}
      {err && <ErrorBox>{err}</ErrorBox>}
      <div className="card overflow-x-auto"><table className="w-full text-sm" data-testid="users-table">
        <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-4 py-2">User</th><th className="px-4 py-2">Role</th>
          <th className="px-4 py-2">2FA</th><th className="px-4 py-2">Failed sign-ins</th><th className="px-4 py-2">Last sign-in</th><th className="px-4 py-2">Actions</th></tr></thead>
        <tbody className="divide-y divide-slate-100">{users.map(u => { const self = u.id === session?.user.id; return (
          <tr key={u.id} data-email={u.email} className={u.is_active ? "" : "opacity-50"}>
            <td className="px-4 py-2"><div>{u.full_name}</div><div className="text-xs text-slate-500">{u.email}{u.is_demo_account ? " · demo" : ""}{u.is_active ? "" : " · deactivated"}</div></td>
            <td className="px-4 py-2 capitalize">{u.role}</td>
            <td className="px-4 py-2 text-xs">{u.totp_enabled ? <span className="text-brand-700">on</span> : <span className="text-slate-500">off</span>}</td>
            <td className={`px-4 py-2 tabular-nums ${u.failed_logins >= 5 ? "font-semibold text-rose-700" : ""}`}>{u.failed_logins}{u.failed_logins >= 5 ? " (locked)" : ""}</td>
            <td className="px-4 py-2 text-xs text-slate-500">{u.last_login_at ? fmtDate(u.last_login_at) : "never"}</td>
            <td className="px-4 py-2"><div className="flex flex-wrap gap-1.5">
              {u.failed_logins > 0 && <button className="btn-ghost px-2 py-1 text-xs" onClick={() => act(`unlock:${u.id}`, async () => { await Api.unlock(u.id); setMsg(`${u.email} unlocked.`); })}>
                <Unlock className="h-3.5 w-3.5" />{armed === `unlock:${u.id}` ? "Confirm unlock" : "Unlock"}</button>}
              {!self && u.is_active && <button className="btn-ghost px-2 py-1 text-xs" onClick={() => act(`reset:${u.id}`, async () => {
                const r = await Api.issueReset(u.id); setLink({ email: u.email, url: `${window.location.origin}${r.reset_path}`, minutes: r.expires_minutes }); })}>
                <KeyRound className="h-3.5 w-3.5" />{armed === `reset:${u.id}` ? "Confirm: issue reset link" : "Reset password"}</button>}
              {!self && u.totp_enabled && <button className="btn-ghost px-2 py-1 text-xs" onClick={() => act(`mfa:${u.id}`, async () => { await Api.resetMfa(u.id); setMsg(`Two-factor authentication removed for ${u.email}; they can enrol again.`); })}>
                <ShieldOff className="h-3.5 w-3.5" />{armed === `mfa:${u.id}` ? "Confirm: reset 2FA" : "Reset 2FA"}</button>}
              {self && <span className="text-xs text-slate-400">you — use Account security</span>}
            </div></td></tr>); })}</tbody></table></div>
    </section>);
}
