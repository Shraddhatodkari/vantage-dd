# Vantage DD — final release report (release 1.2)

Date: 14 October 2026 · tag `release-1.2` · supersedes the 1.1 report (history in git) and the earlier FINAL_* reports.

**Release recommendation: release 1.2 as a completed, evidence-backed portfolio project and internal-pilot
candidate. It is not a certified production deployment.** Every check below was run on this release; raw outputs and
exit codes are in `docs/evidence/`.

What changed since 1.1 (all four follow-ups requested after 1.1):

1. **Dependencies:** react-router 7.18.4 (fixes the 2 moderate advisories), Vite 7.3.6, Vitest 4.1.11, Tailwind 4.3.3,
   jsdom 29 — `npm audit`: **0 vulnerabilities in production and development packages**.
2. **Account security:** two-factor authentication (authenticator-app codes) and administrator-issued single-use
   password reset, with optional mandatory 2FA per role.
3. **Real data:** three more real companies under a **pre-registered blind benchmark** (5 real companies in total).
4. **Security scans and load:** Bandit and an authenticated OWASP ZAP active scan (0 open high/medium/low) and a
   measured load test.

## 1. Defects found and fixed in this release

| # | Defect | Fix | Test |
|---|---|---|---|
| 1 | Saia total debt extracted as **$0.0** (FY2021–22): the first XBRL tag tried (`LongTermDebt`) is 0 for a company whose debt is finance leases | Total debt uses the most inclusive complete aggregate (Saia $31.0M; Yellow, Old Dominion unchanged) | `test_total_debt_uses_the_most_inclusive_aggregate`, `test_already_verified_debt_figures_are_unchanged` |
| 2 | 16 of Diebold Nixdorf's 48 figures missing: standard tags not listed (`ReceivablesNetCurrent`, `NotesPayableCurrent`, combined cash line); "Operating profit (loss)" label not recognised | Tags and label added; combined cash labelled "includes restricted cash"; capex stays n/a (not tagged by the filer) | `test_alternative_standard_tags_and_labelled_cash_fallback` |
| 3 | No going-concern rule (Diebold's 10-K states "These conditions raise substantial doubt…") | `FIN.GOING_CONCERN` (critical), affirmative statements only — hypothetical/boilerplate wording ignored; fires on 1 of 20 stored 10-Ks | 9 wording cases + Diebold API test |
| 4 | Leverage rule silently skipped negative EBITDA (ratio "n/a") — the worst case produced no finding | `FIN.NEGATIVE_EBITDA_WITH_DEBT` (critical) | `test_negative_ebitda_with_debt_is_flagged_not_skipped` |
| 5 | Session invalidation after a password change could miss a session issued in the same second | Password-version stamp in every token (exact match) | `test_password_reset_link_is_single_use_hashed_and_signs_out` |
| 6 | Wrong-code message ("Invalid or expired code") sent the user back to the password step (found by the browser test) | Only the specific "Sign-in expired" message resets the step | `security.test.tsx`, e2e |
| 7 | Front-end catch-all returned the app page with HTTP 200 for any path, incl. unknown API paths and `/.git/config`-style probes (ZAP) | 404 for unknown API paths, dot-files, missing files; app routes only get 200 | `test_unknown_paths_are_404_not_the_app_shell` |
| 8 | CSP allowed `'unsafe-inline'` styles; `form-action`, `base-uri`, `object-src` undefined (ZAP) | Strict CSP + Permissions-Policy; browser suite (fails on console errors) passes | `test_security_headers_have_no_unsafe_inline` |
| 9 | Production served `/openapi.json`; `/metrics` public | Both off in production (`/metrics` with `VANTAGE_METRICS_TOKEN` only) | two subprocess tests |
| 10 | Clause model loaded with `pickle` without an integrity check (Bandit) | SHA-256 pinned in the repo; mismatching file never unpickled | test proves a malicious pickle does not execute |
| 11 | Verification scripts used `assert` (removed by `python -O` → silent pass) (Bandit) | Explicit checks | — |
| 12 | Read-only DB inspection built SQL with unquoted table names (Bandit) | Identifiers quoted | hostile-table-name test |
| 13 | Models and migrations had drifted (two indexes only in migrations) | Declared in the models; new drift test | `test_models_match_migrations_exactly` |
| 14 | `setup.ps1` continued after a failed `pip`/`npm` step (PowerShell ignores native exit codes); no Node version check | Every step checked; stops with a clear message; Node ≥ 20.19 required | run under PowerShell 7 with a forced failure |
| 15 | Comparison: series 4–5 had no colour; table forced every company onto the same years | 6-colour palette; each company shows its own four years | `charts.test.ts`, e2e |
| 16 | Found in the GitHub review (1.2.2): `.env.example` lines of the form `KEY=   # comment` are read by .env parsers as the *value* "# comment", and placeholder text was accepted as a JWT secret / demo password — a copied example file would have run with public credentials | Comments moved to their own lines (all values empty); configuration refuses placeholder or comment-like secrets in every environment and applies the full password policy to the demo password; encoding fixed | `test_placeholder_or_weak_secrets_are_refused`, `test_env_example_has_no_values_for_secrets_and_is_clean_utf8` |

## 2. Files changed (main ones)

Backend: `app/core/mfa.py` (new), `app/core/security.py`, `app/core/config.py`, `app/api/deps.py`,
`app/api/routes_auth.py`, `app/api/schemas.py`, `app/api/routes_deals.py`, `app/db/models.py`, `app/db/seed.py`,
`migrations/versions/0004_mfa_password_reset.py` (new), `app/sources/sec.py`, `app/sources/reconcile.py`,
`app/agents/nodes.py`, `app/agents/quality.py` (risk-v4), `app/agents/report.py`, `app/tools/clauses.py`,
`app/main.py`, `requirements.txt` (cryptography, segno).
Frontend: `pages/Account.tsx`, `pages/ResetPassword.tsx` (new), `pages/Login.tsx`, `pages/Audit.tsx` (Users card),
`pages/Compare.tsx`, `pages/Dashboard.tsx`, `components/*`, `lib/*`, `main.tsx`, `vite.config.ts`, `package.json`.
Tests: `test_mfa_password_reset.py`, `test_extraction_and_going_concern.py`, `test_security_hardening.py` (new),
`test_migrations.py` (+drift), updated count tests, `security.test.tsx` (new), e2e 2FA/reset journey.
Data/eval: `golden.json` (pre-registered blind benchmark), `run_eval.py`, 3 companies' SEC snapshots.
Scripts: `load_test.py` (new), `independent_sec_reconciliation.py`, `verify_source_to_screen.py` (5 companies),
`windows/setup.ps1`, `windows/test.ps1`. Docs: README, METHODOLOGY, OPERATIONS, PERMISSIONS, this report.

## 3. Real-data verification (5 companies, 4 fiscal years each)

5 × 12 reported metrics × 4 years = 240 expected values: **236 reported** (Diebold capex not tagged → n/a, never 0),
**232 printed** in their own filing after the line-item label, **4 composite** (Diebold total debt = long-term debt
+ notes payable, each line printed).

* **Independent re-derivation** (`independent_sec_reconciliation.py`; 65 live SEC `companyconcept` requests, its own
  selection rules and HTML parsing, Decimal arithmetic): 240 reported rows + 230 derived values, **0 discrepancies**;
  `--self-test` catches a planted $0.2M error.
* **Source-to-screen** (`verify_source_to_screen.py`): **PASS for all five** (snapshot → DB → API → display →
  approved memo).
* Yellow FY2022 leverage unchanged: gross **4.51x**, net **3.82x** (the 4.32x figure is not reproducible from the
  filing; see the 1.1 report).

## 4. Formula tests

Unchanged formulas (metrics-v3), all covered by `test_metrics.py` and the regression suite; new extraction rules
and both new risk rules have dedicated tests (section 1).

## 5. AI evaluation

`python ml/eval/run_eval.py` → **QUALITY GATE: PASSED**, methodology `risk-v4/metrics-v3`, offline rules mode.
Issue recall **1.00** (≥ 0.90) · rejection rate **0.00** (≤ 0.10) · critical false positives **0**. Original cases
unchanged: Northwind 92.3, Helios 88.9, Yellow 71.8, Old Dominion 5.2, Aurora 6.0.

**Blind benchmark** (`docs/evidence/blind_benchmark.md`; pre-registered in commit `48b5915`, report-only):

| Company | Outcome after cut-off | Expected | Blind (rules frozen) | After fixes |
|---|---|---|---|---|
| Party City FY2021 | Chapter 11, Jan 2023 | elevated | 58.4 ✔ | 58.4 |
| Diebold Nixdorf FY2022 | Chapter 11, Jun 2023 | elevated | **37.0 ✘** | 60.9 (no longer blind) |
| Saia FY2022 | healthy | low | 4.5 ✔ | 4.5 |

**The honest blind result is 2 of 3.** The stage-2 3/3 only shows the fixes work.

## 6. Test results

| Check | Result |
|---|---|
| Lint (ruff) | 0 issues |
| Backend, SQLite | **162 passed, 4 skipped** (the 4 = live-source tests, run separately) |
| Backend, PostgreSQL 16.15 | **162 passed, 4 skipped**; migration round-trip 0001 → 0004 → 0001 → 0004, rows preserved |
| Live sources (real SEC/GLEIF/FRED) | 4 passed |
| Frontend | TypeScript 0 errors · **20 tests passed** · build OK |
| Browser end-to-end (Chromium) | **4 passed** (full workflow incl. reject → resubmit → approve v2 → download; audit; dashboard/compare; 2FA + reset journey) · secrets in server log: 0 |
| Windows scripts | `setup.ps1`, `test.ps1`, `start.ps1` parsed and **executed under PowerShell 7.4 on Linux** with path shims: setup completed; a forced pip failure stopped setup with exit 1; test.ps1 "ALL CHECKS PASSED"; start.ps1 served the app. **Not run on Windows itself.** |
| Bandit | 0 open issues (5 fixed, 10 annotated with reasons) |
| OWASP ZAP 2.16.1 (authenticated active scan) | first run 1 high (low confidence) + 2 medium → **final 0 high / 0 medium / 0 low**, 4 informational |
| pip-audit / npm audit | 0 / 0 (production and development) |
| Load test (2 vCPU, client on same machine) | **0 errors** at 10/25/50 users; ~40 req/s; p95 0.76 s / 1.6 s / 2.2 s; single pages 8–54 ms; 5 analyses at once all completed in 3.0 s |

## 7. Login, roles, approval, audit, reports

Everything from 1.1 still passes (masked password, no password in UI/logs/reports, bcrypt, httpOnly cookies + CSRF,
rotation and revocation, rate limit, role separation, submitter/starter cannot approve, single concurrent approval,
immutable memos, hash-chained audit). New in 1.2:

* **2FA:** RFC 6238 (verified against the RFC's reference vectors), secret encrypted at rest, replay of a used code
  refused, wrong codes count towards lockout, password alone gives no session, single-use pending-login cookie,
  optional mandatory enrolment per role enforced by the API.
* **Password reset:** 256-bit single-use link, 30 minutes, stored as SHA-256 only, token in the URL fragment (never
  sent to the server log), earlier links cancelled, all older sessions signed out; never for yourself.
* **Audit:** every 2FA and reset step recorded; secrets and tokens never appear (tested).

## 8. Security and GitHub hygiene

No secrets, personal e-mail, old demo password, private keys or API-key patterns in tracked files; no `.env`,
database, storage or index files tracked; largest file 8.3 MB. Screenshots show a one-time 2FA key and reset link
from a throwaway test database (already deleted; not valid anywhere). **Publish the zip (fresh history) rather than
the history bundle**, whose older commits contain a no-longer-valid demo password in a document.

## 9. Local run (Windows PowerShell)

Unzip into a **new** folder (do not unzip over an existing installation with your `.env` and database), then:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1   # needs Python 3.13 and Node 20.19+ / 22 LTS
powershell -ExecutionPolicy Bypass -File scripts\windows\start.ps1   # http://127.0.0.1:8000
powershell -ExecutionPolicy Bypass -File scripts\windows\test.ps1    # backend, eval, source-to-screen, frontend
# demo password: .env, line VANTAGE_SEED_PASSWORD=
```

An existing 1.0/1.1 database is never upgraded automatically; see `docs/OPERATIONS.md` (rehearse on a copy;
migration 0004 is additive).

## 10. Remaining limitations (not done)

1. **Not run on Windows itself.** The scripts were executed under PowerShell 7.4 on Linux; please run `test.ps1` once.
2. **No real LLM provider evaluated** (no API key); rules-only mode is what was measured.
3. **No single sign-on** (needs a company identity provider). 2FA and admin password reset are done.
4. **No penetration test or compliance review** (needs an independent firm). Automated scans only.
5. **Single process**: ~40 req/s on 2 vCPUs; multi-process needs shared locks and a job queue.
6. **Five real companies, blind result 2 of 3**: not a validation of predictive power.
7. Snapshot mode is the tested default; live refresh is tested per endpoint, not as a full UI refresh.

## 11. Release gate

| Gate | Status |
|---|---|
| Evaluation meets thresholds | ✅ PASSED (blind benchmark reported separately: 2/3 blind) |
| Gross/net leverage correct and labelled | ✅ |
| Historical vs current evidence separated | ✅ |
| Real figures traceable | ✅ 236 values, 0 discrepancies, 5/5 source-to-screen |
| Browser workflow to approved, downloadable report | ✅ |
| Roles, audit, password handling, 2FA, reset | ✅ |
| All tests pass; skips explained | ✅ (Windows: PowerShell 7 on Linux, not Windows) |
| No known vulnerable dependencies; scans clean | ✅ |
| No secrets in the repository | ✅ |
