import { NavLink, Outlet, useNavigate } from "react-router";
import { BarChart3, Briefcase, KeyRound, LayoutDashboard, LogOut, Radar, ShieldCheck } from "lucide-react";
import { useAuth } from "../lib/auth";

export default function Layout() {
  const { session, logout, can } = useAuth();
  const nav = useNavigate();
  const user = session?.user;
  const out = async () => { await logout(); nav("/login"); };
  const link = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${isActive ? "bg-white/15 text-white" : "text-slate-400 hover:text-white hover:bg-white/5"}`;
  return (
    <div className="flex min-h-screen">
      <aside className="hidden md:flex w-60 flex-col bg-ink-950 p-4">
        <div className="mb-8 flex items-center gap-2 px-2 text-white">
          <Radar className="h-6 w-6 text-brand-500" />
          <div><div className="font-semibold leading-tight">Vantage DD</div><div className="text-[11px] text-slate-500">Agentic Due Diligence</div></div>
        </div>
        <nav className="space-y-1" aria-label="Main">
          {can("deal:read") && <NavLink to="/" end className={link}><LayoutDashboard className="h-4 w-4" />Portfolio</NavLink>}
          {can("deal:read") && <NavLink to="/deals" className={link}><Briefcase className="h-4 w-4" />Deals</NavLink>}
          {can("deal:read") && <NavLink to="/compare" className={link}><BarChart3 className="h-4 w-4" />Compare</NavLink>}
          {can("audit:read") && <NavLink to="/audit" className={link}><ShieldCheck className="h-4 w-4" />Administration</NavLink>}
          <NavLink to="/account" className={link}><KeyRound className="h-4 w-4" />Account security</NavLink>
        </nav>
        <div className="mt-auto rounded-lg bg-white/5 p-3">
          <div className="text-sm text-white">{user?.full_name}</div>
          <div className="text-xs text-slate-400 break-all">{user?.email}</div>
          <span className="mt-2 inline-block rounded-sm bg-brand-500/20 px-2 py-0.5 text-[11px] uppercase tracking-wide text-brand-100">{user?.role}</span>
          {user?.is_demo_account && <span className="ml-1 inline-block rounded-sm bg-amber-400/20 px-2 py-0.5 text-[11px] text-amber-100">demo</span>}
          {user?.totp_enabled && <span className="ml-1 inline-block rounded-sm bg-white/10 px-2 py-0.5 text-[11px] text-slate-200" title="Two-factor authentication on">2FA</span>}
          <button onClick={out} className="mt-3 flex w-full items-center gap-2 text-xs text-slate-400 hover:text-white"><LogOut className="h-3.5 w-3.5" />Sign out</button>
        </div>
      </aside>
      <div className="flex-1 min-w-0">
        <header className="md:hidden flex items-center justify-between bg-ink-950 px-4 py-3 text-white">
          <span className="font-semibold">Vantage DD</span>
          <div className="flex gap-4 text-sm">
            {can("deal:read") && <NavLink to="/">Portfolio</NavLink>}
            {can("deal:read") && <NavLink to="/deals">Deals</NavLink>}
            {can("deal:read") && <NavLink to="/compare">Compare</NavLink>}
            {can("audit:read") && <NavLink to="/audit">Admin</NavLink>}
            <NavLink to="/account">Account</NavLink>
            <button onClick={out}>Sign out</button></div>
        </header>
        <main className="mx-auto max-w-7xl p-4 md:p-8"><Outlet /></main>
      </div>
    </div>
  );
}
