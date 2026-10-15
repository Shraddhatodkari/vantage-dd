import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { Api, type SessionInfo } from "./api";

interface AuthCtx {
  session: SessionInfo | null; loading: boolean;
  /** "ok" = signed in; "mfa" = password accepted, an authenticator code is needed (loginMfa). */
  login: (e: string, p: string) => Promise<"ok" | "mfa">;
  loginMfa: (code: string) => Promise<void>;
  setSession: (s: SessionInfo | null) => void;
  logout: () => Promise<void>; can: (perm: string) => boolean;
}
const Ctx = createContext<AuthCtx>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    // /auth/session answers 200 for anonymous users and silently rotates an expired access cookie
    Api.session().then(s => setSession(s.authenticated ? s : null))
      .catch(() => setSession(null)).finally(() => setLoading(false));
  }, []);
  const login = async (e: string, p: string) => {
    const r = await Api.login(e, p);
    if ("mfa_required" in r) return "mfa" as const;
    setSession(r); return "ok" as const;
  };
  const loginMfa = async (code: string) => setSession(await Api.loginMfa(code));
  const logout = async () => { try { await Api.logout(); } finally { setSession(null); } };
  // until a required 2FA enrolment is done, the server grants nothing else: mirror that in the UI
  const can = (perm: string) => !session?.mfa_setup_required && !!session?.permissions.includes(perm);
  return <Ctx.Provider value={{ session, loading, login, loginMfa, setSession, logout, can }}>{children}</Ctx.Provider>;
}
export const useAuth = () => useContext(Ctx);
