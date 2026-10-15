# Vantage DD — final enterprise build: report

Date: 14 October 2026 · git tag `enterprise-v4-final` · supersedes the counts in `FINAL_AUDIT_REPORT.md` (kept for history).

All work was done on a copy of the repository and on temporary databases (SQLite files in a scratch folder and a
throwaway PostgreSQL 16 cluster). Your `backend\vantage.db`, its backup and `vantage_migration_test.db` were never
opened or changed.

## 1. Readiness assessment

| Area | Verdict | Basis |
|---|---|---|
| Local functionality | **Working, tested** | 119 backend tests, 14 frontend tests, 3 browser journeys; all pass |
| Data correctness (Yellow, ODFL FY2019–22) | **Verified against the filings** | 96/96 reported values found in the text of the filing each came from; 14 derived values recomputed; screen = API = memo |
| AI operation | **Rules-only mode verified; LLM mode not verified** | No API key was used. LLM paths are tested with a fake model (failures, malformed output, invented quotes, ungrounded answers). Every screen states the AI mode |
| Security | **Controls implemented and tested; no penetration test** | Server-side permissions, deal isolation, CSRF, token expiry and revocation, rate limits, safe 500s, no secrets in logs, append-only audit. Python dependencies: no known vulnerabilities; frontend: 2 moderate advisories (section 6) |
| Production deployment | **Not production-ready** | PostgreSQL tested (full suite + migrations), but no HTTPS deployment, SSO/MFA, multi-process safety, monitoring or load test has been done |

**Overall: an internal pilot candidate.** Suitable for a supervised pilot on historical public filings. Not
production-ready: see the go-live checklist in section 8.

## 2. Baseline before this build

Tag `enterprise-v3-final`: backend 106 passed / 4 skipped, frontend 12, browser e2e 2, source-to-screen PASS,
eval PASS. Never run against PostgreSQL, and never dependency-audited.

## 3. What changed (and why)

| # | Change | Why / defect found |
|---|---|---|
| 1 | **Analyst submission step.** A run now ends as a *draft*; an analyst submits it (optional note); only then can a different partner approve or reject. A partner who started *or submitted* a run cannot approve it. Migration `0003` | The brief's lifecycle requires "analyst submission"; previously runs went straight to the partner |
| 2 | **PostgreSQL verified.** The full test suite runs on PostgreSQL 16 (119 passed); migrations round-trip 0001→0003→0001→0003 with data | **Defect found:** `companies.lei_match` was `VARCHAR(20)` but stores `jurisdiction_mismatch` (21 chars). SQLite ignores lengths; PostgreSQL rejected the write, so ODFL could not be loaded on Postgres. Widened to 40 in `0003` |
| 3 | **Dependency security.** python-jose → PyJWT 2.15.1; pypdf 5.9.0 → 6.19.0; react-router 6.28.0 → 6.30.6 | pip-audit found 88 advisories (pypdf, python-jose and its ecdsa dependency, which has no fix); npm audit found a high-severity react-router open redirect. Python audit now clean |
| 4 | **Evidence categories per workstream** (e.g. litigation, credit-agreement text, maturities, covenants, pensions, labour, internal control, independent market study), each reported as *finding raised* / *reviewed — no rule triggered* / *insufficient evidence* / *not performed* | Distinguishes "clean" from "nothing to look at". Legal counsel now also reads the 10-K notes (litigation and debt disclosures sit there). Market strategist reviews the company's own Items 1/1A, and the missing independent market study stays a **scored** gap. Missing credit-agreement text and customer contracts are disclosed as follow-ups, not scored |
| 5 | **Payments-only category scoped.** "Sector regulatory compliance (PCI, KYC/AML, licences)" now applies only to payments and third-party-risk deals | It was being counted as a gap for trucking companies, which inflated the gap count |
| 6 | **Score contribution per finding** (points = score × weight ÷ total weight), shown on every finding and in the memo | "How each finding affects the score" was not visible. Points sum to the score within rounding (tested) |
| 7 | **No false precision on large ratios.** ≥ 100x shows whole numbers, 10–100x one decimal; exact values stay in provenance | ODFL showed "2,844.53x" EBITDA/interest |
| 8 | **Credit thesis (positive evidence)** from the same facts and thresholds as the risk rules; it does not change the score | The memo listed only risks |
| 9 | **IC memo rebuilt** into 11 decision-oriented sections: executive summary, thesis, material risks with points, 4-year trends, debt and covenants, detailed evidence, coverage and unresolved questions, follow-up and information requests, methodology (incl. "not a probability of default"), sources with accession and filing date, approval history | Required memo content |
| 10 | **Printable HTML export** of the approved memo, with the same SHA-256 as the Markdown. Filing text is escaped before rendering, so no markup from a source document can execute | Export formats. Tested with an injected `<script>` |
| 11 | **Dashboard.** KPIs from stored data: companies reviewed, ready to submit, awaiting approval, approved, diligence gaps, facts confirmed in filings (96/96) with source mode and retrieval age. Also a recent-activity feed, an open-gaps list, clickable risk bars, and auto-refresh (30 s and on focus) | **Removed "Average risk"**: averaging Yellow (71.8) and ODFL (5.2) gives 38.5, a number that describes neither company. A screenshot showing Yellow "open" was a stale page (the dashboard loaded only once); it now refreshes |
| 12 | **Company comparison workspace** (Yellow vs ODFL): scores, components, key findings, evidence gaps, 6 charts and a full metric table | Required |
| 13 | **Financial charts** on each deal (7 charts). One measure per chart, no dual axes, missing = gap (never 0), legend for 2+ series, tooltip with exact value; palette validated for colour-blind separation | Required. Charts and table read the same API values (asserted in e2e) |
| 14 | **Evidence drill-down to the filing line**: each reported value shows the 10-K passage it was found in (e.g. "Purchase of property and equipment (775,148 )…") and a link to the filing on SEC EDGAR | "Show the original source passage" |
| 15 | **AI provider status** (`/api/v1/ai/status`, shown on Analysis, Ask and Admin pages) and an administrator connectivity check (one tiny, audited call; errors reported by type only) | AI mode must be transparent. At most 5 LLM calls per run (supervisor + 4 specialists), 2,048 tokens each, 60 s timeout, 2 retries |

## 4. Commands executed and results (this environment: Linux, Python 3.13, Node 22)

| Suite | Command | Result |
|---|---|---|
| Lint | `ruff check backend ml scripts e2e --select E,F,I,B --ignore E501,B008` | exit 0 ([lint.txt](evidence/lint.txt)) |
| Backend on SQLite | `cd backend && python -m pytest -q` | **119 passed, 4 skipped, exit 0** ([log](evidence/test_backend.txt)) |
| Backend on PostgreSQL 16.15 | `VANTAGE_TEST_DATABASE_URL=postgresql+psycopg://…/vantage_test python -m pytest -q` | **119 passed, 4 skipped, exit 0** ([log](evidence/test_backend_postgres.txt)) |
| Migration round-trip on PostgreSQL | `python scripts/pg_migration_check.py postgresql+psycopg://…/empty_db` | **OK: 0001 → 0003 → 0001 → 0003, rows preserved** |
| Live sources (real SEC, GLEIF, FRED) | `VANTAGE_LIVE_TESTS=1 python -m pytest tests/test_live_sources.py` | **4 passed, exit 0** ([log](evidence/test_live_sources.txt)) |
| Source-to-screen | `python scripts/verify_source_to_screen.py` | **PASS** Yellow 48/48, ODFL 48/48 ([summary](evidence/source_to_screen.txt), [Yellow](evidence/yellow_source_to_screen.md), [ODFL](evidence/odfl_source_to_screen.md)) |
| Agent evaluation gate | `python ml/eval/run_eval.py` | **PASSED, exit 0** ([report](evidence/eval_report.json)) |
| Frontend | `npx tsc --noEmit -p . ; npx vitest run ; npm run build` | tsc 0; **14 passed**; build 0 ([log](evidence/test_frontend.txt)) |
| Browser end-to-end (Chromium) | `pytest e2e -v` against a running server | **3 passed, exit 0** ([log](evidence/test_e2e_browser.txt)) |
| Secrets in server log | grep for the demo password and JWTs after e2e | 0 occurrences |
| Python dependencies | `pip-audit -r backend/requirements.txt` | **No known vulnerabilities** ([log](evidence/dependency_audit.txt)) |
| Frontend production dependencies | `npm audit --omit=dev` | 2 moderate (react-router; section 6) |

Skipped: the 4 skipped backend tests are the live tests in the normal run (they ran separately above). Mocked:
`test_sources_http.py` (network errors, retries, tampered snapshots) and `test_llm_safety.py` (fake LLM). Live: 4
tests against SEC/GLEIF/FRED, plus five SEC filing retrievals earlier in the audit. Everything else uses the stored,
sha256-verified snapshots.

Browser journeys verified (screenshots `docs/screenshots/01–15`):
1. Login page shows no password; the eye toggle works.
2. The analyst runs Yellow; the AI mode shows "rules only"; findings carry score points.
3. Financials: revenue, FCF and total debt match the 10-K; the 10-K passage and EDGAR link appear; charts render.
4. The analyst submits with a note; the partner approves.
5. The memo has all sections, and the downloaded `.md` hash equals the on-screen hash.
6. The `.html` export carries the same hash and contains no script.
7. ODFL: the coverage gap appears; FCF inputs are exact; capex shows its 10-K line; EBITDA/interest shows "1,354x"; the LEI is not auto-accepted; sources are labelled as snapshots.
8. The analyst submits ODFL; the partner cannot reject without a reason, then rejects with one; the analyst re-runs and the history shows both versions.
9. Portfolio KPIs show 96/96 and the activity feed shows the submission; the comparison table matches deal values; the password is absent from every page.
10. Admin runs the AI check ("No LLM provider configured") and verifies the audit chain. Admin cannot run analyses.

## 5. Source-to-screen: Yellow and Old Dominion

| FY2022 ($M) | Old Dominion (10-K 0000950170-23-003783, filed 2023-02-22) | Yellow (10-K 0000950170-23-002332, filed 2023-02-09) |
|---|---|---|
| Revenue | 6,260.077 → $6,260.1M | 5,244.7 → $5,244.7M |
| EBITDA (op. income + D&A, unadjusted) | 2,116.682 | 341.2 |
| Interest expense | 1.563 (`InterestAndDebtExpense`) | 162.9 |
| Total debt / cash | 99.963 / 186.312 | 1,538.0 / 235.1 |
| Operating cash flow − capex = FCF | 1,691.582 − 775.148 = **916.434 → $916.4M** | 121.3 − 191.8 = **−70.5** |
| Net debt / EBITDA | −0.04x (net cash $86.3M) | 3.82x |
| EBITDA / interest | 1,354x | 2.09x |
| Reported values found in their own filing | 48 / 48 | 48 / 48 |
| Risk score (rules only, risk-v3) | **5.2 → Proceed** | **71.8 → Renegotiate price and terms** |
| Identity | GLEIF record found but jurisdiction differs (US-DE vs SEC VA) — **not accepted** | GLEIF exact match `529900SEX4UQ2WLPRC40` |

Scores did not change in this build (no rule or weight was tuned). Every material Yellow conclusion has the
quoted 10-K passage or a recomputed calculation as evidence: maturities on 2024-06-30 and 2024-09-30, leverage,
coverage, negative FCF, inability to repay if accelerated, covenant waiver history, PIK interest, minimum-EBITDA
covenant (labelled an approximation: lenders use adjusted EBITDA), critical-and-declining multi-employer pensions,
and the labour agreement to 2024-03-31. ODFL's only scored items are the missing independent market study (3.7
points) and two low-severity items. Its cash decline is shown in context (net cash, FCF +$916.4M).

## 6. Known limitations and unresolved risks

* **AI:** no real LLM was exercised; an API key and an evaluation on real outputs are needed before relying on LLM
  findings. Rules were written after reading Yellow's filing; ODFL is the only held-out real company. Two companies
  are not a validation set, and the score is not a probability of default.
* **Evidence gaps that cannot be closed from 10-Ks alone:** independent market study, full credit-agreement and
  indenture text, and customer contracts. These are disclosed as gaps and follow-ups, never as clean results.
* **Frontend advisories:** two moderate react-router advisories (backslash open redirect in `<Link>`/`useNavigate`;
  SSR hydration constructor injection). The fix is a breaking upgrade to v7. Not exploitable as used here (no SSR;
  navigation only to API-issued IDs). Accepted for the pilot and listed in the checklist.
* **Dev-tool advisories** (vitest, esbuild, postcss) affect only the build machine; they are not shipped.
* **FRED** values are the current vintage, not as-published at the cut-off (FEDFUNDS is rarely revised).
* **Coincidental matches** in filing reconciliation were measured at 0.62% on perturbed values. "Matched" is strong
  evidence, not absolute proof.
* **Windows** was not executed by me. The scripts and the `windows-latest` CI job are provided.
* **Single-process design:** the audit-chain lock and rate limiter are in-process; run one worker.
* GLEIF's response for Yellow changed between retrievals (only its `publishDate` metadata). Both copies are stored.

## 7. Windows PowerShell commands

```powershell
# one-time setup (venv, dependencies, .env with random secrets, frontend build, NEW database only)
powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1
# run                                    -> http://127.0.0.1:8000
powershell -ExecutionPolicy Bypass -File scripts\windows\start.ps1
# all automated checks (backend, eval, source-to-screen, frontend)
powershell -ExecutionPolicy Bypass -File scripts\windows\test.ps1
# frontend production build only
cd frontend; npm ci; npm run build; cd ..
# read-only look at an existing database (never modifies it)
.venv\Scripts\python scripts\manage.py inspect-db --path backend\vantage.db
# dependency / import check
.venv\Scripts\python scripts\manage.py doctor
# PostgreSQL (optional)
.venv\Scripts\python -m pip install -r backend\requirements-postgres.txt
```

Configuration still needed (put values in `.env` or OS environment variables, never in chat or git):

* `VANTAGE_SEC_USER_AGENT="Your Name you@domain"` for live SEC refresh.
* `VANTAGE_LLM_PROVIDER=anthropic` and `VANTAGE_ANTHROPIC_API_KEY=…` to enable LLM mode (then run the Admin →
  connectivity check).
* For production: `VANTAGE_ENV=prod`, `VANTAGE_DEMO_MODE=false`, a random `VANTAGE_JWT_SECRET`,
  `VANTAGE_COOKIE_SECURE=true`, https `VANTAGE_CORS_ORIGINS`, a PostgreSQL `VANTAGE_DATABASE_URL`, then
  `manage.py create-admin`.

Your existing `vantage.db` has no migration history, so the app refuses it and leaves it untouched. Start on a new
file (`VANTAGE_DATABASE_URL=sqlite:///…/vantage-v4.db`) or follow "Upgrading an existing database" in
OPERATIONS.md.

## 8. Go-live checklist

Done and tested: server-side RBAC and deal isolation; analyst → partner workflow with segregation of duties,
reasons and concurrency safety; immutable approved memos with hashes; append-only audit; source provenance and
filing reconciliation; historical cut-off; coverage disclosure; PostgreSQL support and migrations; backup and
restore; safe start-up on existing databases; Python dependencies clean.

Still required before production:

- [ ] Run `setup.ps1` / `test.ps1` on your Windows machine.
- [ ] HTTPS reverse proxy, secure cookies and a production `.env`, with secrets in a secret manager.
- [ ] SSO/MFA, password reset and user lifecycle.
- [ ] Multi-process safety (Postgres advisory locks and a shared rate limiter), or a single worker.
- [ ] Ship the audit log to WORM/SIEM storage; set up monitoring and alerting on `/healthz`, `/readyz`, `/metrics`.
- [ ] react-router v7 upgrade.
- [ ] Real-LLM evaluation and a blind validation set (defaulted vs matched companies).
- [ ] UI to accept or reject a flagged LEI after manual verification.
- [ ] Load test, penetration test, accessibility audit, data-protection review.
- [ ] Scheduled backups with restore drills; a documented rollback plan.
