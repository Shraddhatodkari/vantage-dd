// Typed API client. Sessions live in httpOnly cookies (JavaScript never sees tokens); state-changing
// requests send the CSRF token from the readable vantage_csrf cookie. A 401 triggers one refresh attempt.
export type Role = "analyst" | "partner" | "admin";
export interface User { id: string; email: string; full_name: string; role: Role; is_active: boolean; is_demo_account: boolean;
  totp_enabled: boolean; failed_logins: number; last_login_at: string | null }
export interface SessionInfo { user: User; permissions: string[]; access_expires_at: string; mfa_setup_required: boolean }
export interface MfaChallenge { mfa_required: true }
export interface MfaSetup { secret: string; otpauth_uri: string; qr_svg: string }
export interface ResetLink { reset_path: string; expires_at: string; expires_minutes: number }
export interface PublicConfig { app_name: string; env: string; demo_mode: boolean; demo_accounts: { email: string; role: Role }[]; source_mode: string }
export type Classification = "verified_real" | "illustrative" | "user_supplied";
export interface Doc {
  id: string; filename: string; doc_type: string; title: string | null; n_chars: number; n_chunks: number;
  pii_redactions: number; injection_flags: number; data_classification: Classification; source_url: string | null;
  accession: string | null; period_end: string | null; uploaded_at: string;
}
export interface Company {
  name: string; cik: string | null; tickers: string[]; sic: string | null; sic_description: string | null;
  state_of_incorporation: string | null; lei: string | null; lei_legal_name: string | null; lei_status: string | null; lei_match: string | null; lei_record: Record<string, any>;
}
export interface Source { source: string; label: string; notes: string | null; url: string; retrieved_at: string; retrieval_mode: string; accession: string | null; filing_date: string | null; age_days: number; stale: boolean;
  time_basis?: string; used_in_scoring?: boolean; basis_note?: string | null }
export interface Deal {
  id: string; name: string; target_company: string; deal_type: string; sector: string; data_classification: Classification;
  is_historical: boolean; reporting_period_end: string | null; currency: string; deal_size_musd: number | null;
  deal_size_basis: string | null; historical_cutoff?: string | null; status: string;
  latest_version?: number | null; latest_status?: string | null; approved_version?: number | null; approved_risk_score?: number | null; approved_run_id?: string | null; risk_score: number | null; risk_score_run_id: string | null; created_at: string;
  documents?: Doc[]; company?: Company | null; sources?: Source[]; members?: { user_id: string; email: string; role: Role }[];
}
export interface DealMeta { id: string; name: string; data_classification: Classification; status: string; created_at: string }
export interface Fact {
  id: string; metric: string; fiscal_year: number; period_start: string | null; period_end: string | null; value: number | null;
  unit: string; currency: string | null; kind: "reported" | "calculated"; status: string; status_reason: string | null;
  xbrl_tag: string | null; accession: string | null; form: string | null; filed: string | null; source_document: string | null;
  formula: string | null; inputs: { metric: string; fiscal_year: number; value: number | null; unit?: string }[]; restated: boolean; restatement_note: string | null;
  document_check?: string; document_check_detail?: string | null; revision_note?: string | null;
  document_passage?: string | null; filing_url?: string | null;
}
export interface Evidence {
  kind: "document_excerpt" | "reported_fact" | "calculation" | "assumption" | "macro_series";
  [k: string]: any;
}
export interface Finding {
  id: string; code: string; agent: string; category: string; severity: "low" | "medium" | "high" | "critical";
  claim_type: "source_fact" | "calculation" | "interpretation" | "assumption"; title: string; detail: string;
  evidence: Evidence[]; limitations: string | null; verification_status: "verified" | "supported" | "rejected";
  verification_notes: string[]; created_at: string; score_weight?: number | null; score_points?: number | null;
}
export interface RunEvent { seq: number; agent: string; status: string; message: string; latency_ms: number; created_at: string }
export interface ReportMeta { id: string; version: number; content_sha256: string; findings_sha256: string; inputs_hash: string | null; methodology_version: string; approved_by: string; approved_at: string }
export interface Run {
  id: string; deal_id: string; version: number; status: string; question: string; methodology_version: string;
  inputs_hash: string | null; as_of_date: string | null; risk_score: number | null; recommendation: string | null;
  metrics: Record<string, any>; agent_errors: { agent: string; error: string }[]; started_by: string; reviewer_id: string | null;
  review_note: string | null; reviewed_at: string | null;
  submitted_by?: string | null; submitted_at?: string | null; submission_note?: string | null; created_at: string; finished_at: string | null;
  findings?: Finding[]; events?: RunEvent[]; reports?: ReportMeta[]; inputs_changed_since_run?: boolean;
  coverage?: Coverage[];
}
export interface Coverage {
  agent: string; status: string; doc_types: string[]; documents_reviewed: number; document_names: string[]; facts_used: number;
  calculated_values?: number; rules_evaluated: number; rule_matches: number; candidate_findings: number; llm: string; limitation: string | null;
  categories?: Category[];
}
export interface AskAnswer { answer: string; answer_type: "extractive" | "llm_grounded" | "abstained"; citations: any[]; withheld_reason?: string | null }
export interface Report extends ReportMeta { content_md: string }
export interface Group {
  deals: number; deals_scored: number; avg_risk: number | null; awaiting_review: number; findings_by_severity: Record<string, number>;
  findings_by_category: Record<string, number>; findings_accepted: number; findings_rejected: number; exposure_musd: number | null; exposure_note: string;
  ready_to_submit: number; approved: number; deals_with_gaps: number; gap_categories: number; reported_facts: number;
  facts_confirmed_in_filing: number; facts_composite?: number; sources: { count?: number; modes?: string[]; oldest_retrieval_days?: number | null; stale?: number };
  deals_detail: { deal_id: string; name: string; status: string; risk_score: number | null; recommendation: string | null;
    run_status: string | null; run_version: number | null; gaps: string[]; severities: Record<string, number> }[];
}
export interface AiStatus { provider: string; model: string | null; api_key_set: boolean; mode: "rules_only" | "llm_configured"; note: string; max_calls_per_run: number }
export interface Activity { at: string; deal_id: string; deal: string; action: string; by: string | null; version: number; detail: string | null }
export interface CompareRow {
  deal_id: string; name: string; company: string; period_end: string | null; historical_cutoff: string | null; status: string;
  facts: { metric: string; fiscal_year: number; value: number | null; unit: string; kind: string; status: string; document_check: string }[];
  run: { id: string; version: number; status: string; risk_score: number | null; recommendation: string | null; methodology_version: string;
    breakdown: Record<string, number>; coverage: { agent: string; documents_reviewed: number; categories: Category[] }[] } | null;
  top_findings: { code: string; title: string; severity: string; verification_status: string }[]; sources_mode: string[];
  approved_version?: number | null;
}
export interface Category { key: string; label: string; status: string; required: boolean; doc_types: string[]; basis: string; findings: number }
export interface Stats { verified_real: Group; illustrative: Group; user_supplied: Group; definitions: Record<string, string> }
export interface AuditEntry { id: number; user_email: string | null; action: string; resource: string; outcome: string; detail: Record<string, any>; ip: string | null; created_at: string; hash: string }

const BASE = "/api/v1";

function csrf(): string {
  const m = document.cookie.match(/(?:^|;\s*)vantage_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }

let refreshing: Promise<boolean> | null = null;
async function refreshSession(): Promise<boolean> {
  refreshing ??= fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "same-origin", headers: { "X-CSRF-Token": csrf() } })
    .then(r => r.ok).finally(() => { refreshing = null; });
  return refreshing;
}

export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  if (!(init.body instanceof FormData) && init.body) headers["Content-Type"] = "application/json";
  if (init.method && init.method !== "GET") headers["X-CSRF-Token"] = csrf();
  const r = await fetch(`${BASE}${path}`, { ...init, headers, credentials: "same-origin" });
  if (r.status === 401 && retry && !path.startsWith("/auth/") && (await refreshSession())) return api<T>(path, init, false);
  if (!r.ok) {
    let msg = r.statusText || `HTTP ${r.status}`;
    try { const j = await r.json(); msg = typeof j.detail === "string" ? j.detail : (j.detail?.[0]?.msg ?? msg); } catch { /* not JSON */ }
    throw new ApiError(r.status, msg);
  }
  if (r.status === 204) return undefined as T;
  return ((r.headers.get("content-type") || "").includes("json") ? r.json() : r.text()) as Promise<T>;
}

export const Api = {
  meta: () => api<PublicConfig>("/meta"),
  login: (email: string, password: string) => api<SessionInfo | MfaChallenge>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }, false),
  loginMfa: (code: string) => api<SessionInfo>("/auth/login/mfa", { method: "POST", body: JSON.stringify({ code }) }, false),
  mfaSetup: () => api<MfaSetup>("/auth/mfa/setup", { method: "POST" }),
  mfaEnable: (code: string) => api<SessionInfo>("/auth/mfa/enable", { method: "POST", body: JSON.stringify({ code }) }),
  mfaDisable: (password: string, code: string) => api<User>("/auth/mfa/disable", { method: "POST", body: JSON.stringify({ password, code }) }),
  changePassword: (current_password: string, new_password: string, code?: string) =>
    api<SessionInfo>("/auth/password", { method: "POST", body: JSON.stringify({ current_password, new_password, code: code || null }) }),
  completeReset: (token: string, new_password: string) =>
    api<void>("/auth/password-reset", { method: "POST", body: JSON.stringify({ token, new_password }) }, false),
  users: () => api<User[]>("/admin/users"),
  issueReset: (userId: string) => api<ResetLink>(`/admin/users/${userId}/password-reset`, { method: "POST" }),
  resetMfa: (userId: string) => api<User>(`/admin/users/${userId}/mfa/reset`, { method: "POST" }),
  unlock: (userId: string) => api<User>(`/admin/users/${userId}/unlock`, { method: "POST" }),
  logout: () => api<void>("/auth/logout", { method: "POST" }, false),
  me: () => api<SessionInfo>("/auth/me"),
  session: () => api<SessionInfo & { authenticated: boolean }>("/auth/session"),
  stats: () => api<Stats>("/portfolio/stats"),
  aiStatus: () => api<AiStatus>("/ai/status"),
  aiCheck: () => api<{ ok: boolean; status: string; error_type?: string; latency_ms?: number }>("/admin/ai/check", { method: "POST" }),
  activity: () => api<Activity[]>("/portfolio/activity?limit=12"),
  compare: () => api<CompareRow[]>("/portfolio/compare"),
  deals: () => api<Deal[]>("/deals"),
  allDealMetadata: () => api<DealMeta[]>("/admin/deals"),
  deal: (id: string) => api<Deal>(`/deals/${id}`),
  financials: (id: string) => api<Fact[]>(`/deals/${id}/financials`),
  createDeal: (body: Partial<Deal>) => api<Deal>("/deals", { method: "POST", body: JSON.stringify(body) }),
  upload: (id: string, file: File) => { const f = new FormData(); f.append("file", file); return api<Doc>(`/deals/${id}/documents`, { method: "POST", body: f }); },
  refreshSources: (id: string) => api<Record<string, any>>(`/deals/${id}/sources/refresh`, { method: "POST" }),
  runs: (id: string) => api<Run[]>(`/deals/${id}/runs`),
  run: (runId: string) => api<Run>(`/runs/${runId}`),
  startRun: (id: string) => api<Run>(`/deals/${id}/runs`, { method: "POST", body: JSON.stringify({}) }),
  submit: (runId: string, note: string) => api<Run>(`/runs/${runId}/submit`, { method: "POST", body: JSON.stringify({ note }) }),
  review: (runId: string, decision: "approved" | "rejected", note: string) =>
    api<Run>(`/runs/${runId}/review`, { method: "POST", body: JSON.stringify({ decision, note }) }),
  report: (runId: string) => api<Report>(`/runs/${runId}/report`),
  reportUrl: (runId: string) => `${BASE}/runs/${runId}/report.md`,
  ask: (id: string, question: string) => api<AskAnswer>(`/deals/${id}/ask`, { method: "POST", body: JSON.stringify({ question }) }),
  audit: () => api<AuditEntry[]>("/admin/audit?limit=500"),
  verifyAudit: () => api<{ valid: boolean; entries_checked: number }>("/admin/audit/verify"),
};
