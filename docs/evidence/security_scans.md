# Automated security scans (release 1.2)

**These are automated scans, not a penetration test.** A penetration test is a manual engagement by an independent
tester; none has been performed. Scans ran on 14 October 2026 against a throwaway server and database.

## 1. Static analysis — Bandit 1.8.6 (Python: `backend/app`, `backend/mcp_server`, `scripts`, `ml`; 7,100+ lines)

First run: 0 high, 5 medium, 13 low. After triage: **0 open issues** (`docs/evidence/bandit.txt`).

| Finding | Decision |
|---|---|
| B301/B403 `pickle.load` of the clause model | **Fixed.** The model's SHA-256 is pinned in the repository (`clause_classifier.pkl.sha256`); a file that does not match is never unpickled. Test proves a tampered pickle does not execute. |
| B615 model-hub download without a pinned revision | **Fixed.** The API loads the LoRA adapter with `local_files_only=True` (never downloads). The training script takes `--revision` (pin a commit hash). |
| B608 SQL built from a string (read-only DB inspection) | **Fixed.** Table names are quoted as SQL identifiers; test with a hostile table name. The connection was already read-only. |
| B101 `assert` in verification scripts (×8) | **Fixed.** Replaced with explicit checks: `python -O` would otherwise have removed them and let a verification pass silently. |
| B105 "hard-coded password" (insecure default JWT secret) | Accepted, annotated: deliberately unusable; production configuration refuses it. |
| B311 `random` (retry jitter, dataset shuffle) | Accepted, annotated: not security-relevant. |

## 2. Dynamic scan — OWASP ZAP 2.16.1 (authenticated)

Plan (`docs/evidence/zap_plan.yaml`, session values redacted): OpenAPI import of every endpoint, spider, passive scan,
**active scan** (default attack policy) with an analyst session and CSRF header, then passive scan again.

First run: 1 high (low confidence), 2 medium, 4 informational.

| Alert | Cause | Fix |
|---|---|---|
| High: Path Traversal (`/api/v1/deals/%2F…`) | False positive in substance, but real sloppiness: the front-end catch-all answered **any** unknown path, including unknown API paths, with the app page and HTTP 200. | Unknown API paths, dot-files and missing files return 404 JSON; only the app's own routes get the page with 200 (other paths get it with 404). Tests. |
| Medium: Hidden File Found (`/._darcs`, `/BitKeeper`) | Same catch-all. | Same fix. |
| Medium: CSP `style-src 'unsafe-inline'` | Not needed: React applies styles through the DOM. | Removed; the browser test suite (fails on any console error) confirms no CSP violation. |
| Medium: CSP directive with no fallback | `form-action`, `base-uri`, `object-src` were not set. | Added, plus `Permissions-Policy`. Test. |

Also found by review during the scan: production still served `/openapi.json` (fixed: off in production, test) and
`/metrics` was public (fixed: in production it needs `VANTAGE_METRICS_TOKEN` or returns 404, test).

**Final run: 0 high, 0 medium, 0 low.** 4 informational: "Modern Web Application" (it is a single-page app),
"Authentication Request Identified" (the login form), "User Agent Fuzzer" on `/metrics` (open in dev mode only),
"Suspicious Comments" in the bundled chart library (third-party comments, no secrets). Full report:
`docs/evidence/zap_report.md`.

## 3. Dependencies

* Python: `pip-audit` — no known vulnerabilities (`docs/evidence/dependency_audit.txt`).
* JavaScript: `npm audit` — **0 vulnerabilities, production and development** (react-router 7.18.4, Vite 7.3.6,
  Vitest 4.1.11, Tailwind 4.3.3).

## Not covered

Manual penetration testing, authenticated scans as partner/admin roles (access control is covered by the automated
API and browser tests instead), infrastructure/TLS configuration (no production hosting), denial-of-service resilience.
