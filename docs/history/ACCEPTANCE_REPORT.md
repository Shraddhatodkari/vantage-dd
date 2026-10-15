# Enterprise upgrade — acceptance report

Scope: upgrade of the existing Vantage DD repository (baseline tag `baseline-v1`). All results below come from
commands run on 2026-10-13 in a Linux (Python 3.13.16, Node 22.22) environment. **Nothing was run on Windows**;
see §12 and §11.

## 1. Data provenance audit — before and after

| Screen / output | Value | Before (baseline-v1) | After |
|---|---|---|---|
| Login | Demo password | **Printed on the login page** (a fixed password, now redacted) and hard-coded in config | Removed. Random per-install password in `.env` only; UI shows demo e-mails only in demo mode |
| Dashboard | Deal count, average risk, findings by severity | Real and synthetic deals mixed in one total | Separate *Verified real*, *Illustrative*, *User-supplied* sections; averages defined on screen |
| Dashboard | "Size ($M)" for Yellow = 1,538 | Unlabelled; actually book debt shown as "deal size" | Labelled "Size / exposure" with basis on hover: `us-gaap:LongTermDebt` at 2022-12-31, 10-K 0000950170-23-002332; never summed across deals |
| Dashboard | "Groundedness 100%" | Numeric-substring check only | Replaced by accepted/rejected counts from the evidence-checking quality gate |
| Deal header | Company identity, period, currency | Not shown | CIK, tickers, SIC, state, GLEIF LEI (or flagged mismatch), period end, currency, historical banner |
| Financials | Revenue, EBITDA, debt, cash, FCF… | Hand-built CSV in the repo; no per-value source | XBRL facts with tag, accession, filing date, period (R) and calculations with formula and inputs (C); missing = `n/a` + reason |
| Findings | Confidence 80–95% | Hard-coded constants per rule, shown as percentages | Removed. Claim type (source fact / calculation / interpretation / assumption) + verification status |
| Findings | Pension evidence "Critical and Declining;" | Excerpt came from a **paraphrased summary line** written into a file labelled "verbatim" | Excerpts are exact substrings of the 10-K text with character offsets; verified by the quality gate |
| Findings | "growth is being funded by external capital" | Interpretive wording on a 2.4%-growth company | Replaced by the cash-flow facts: OCF $121.3M did not cover capex $191.8M |
| Agent activity | Legal counsel 14,282 ms, 0 findings | ML classifier called once per sentence | Batched; rule-only clause scan for legal; measured 18–57 ms per run |
| Memo | Conditions precedent | Triggered by keywords in titles (e.g. "covenant" in a headroom finding) | Each condition tied to a specific verified finding code |
| Memo | Approval | Text line; memo regenerated in memory | Immutable `ReportVersion` with approver, UTC time, analysis version, findings sha256; export identical to screen |
| Audit | Log | Mutable table | Append-only (DB triggers) + hash chain + verify endpoint |
| Northwind / Helios | All figures | Presented like real deals | Labelled *Illustrative (synthetic)* everywhere and kept out of real aggregates |

Classification of displayed values after the upgrade: **reported by source** (XBRL facts, 10-K excerpts, FRED
observations, GLEIF records), **calculated** (registry formulas), **AI/analyst interpretation** (red-team and
LLM findings, labelled), **assumption** (thresholds, labelled), **synthetic** (illustrative deals, labelled),
**unavailable** (`n/a` with status reason).

## 2. Authoritative sources actually retrieved and used

| Source | Endpoint | Used for |
|---|---|---|
| SEC EDGAR submissions | `https://data.sec.gov/submissions/CIK0000716006.json`, `…CIK0000878927.json` | locating the FY2022 10-K, filing date, amendments (Yellow has a 10-K/A filed 2023-03-16; the original 10-K is used and the amendment is disclosed) |
| SEC XBRL company facts | `https://data.sec.gov/api/xbrl/companyfacts/CIK0000716006.json`, `…CIK0000878927.json` | 4 years of point-in-time financial facts |
| SEC filing documents | Yellow `…/716006/000095017023002332/yell-20221231.htm`; ODFL 10-K accession 0000950170-23-003783 | 10-K Items (business, risk factors, legal proceedings, MD&A, financial statements and notes, controls) |
| GLEIF | `https://api.gleif.org/api/v1/lei-records?filter[entity.legalName]=…` | LEI identity check (Yellow: exact match 529900SEX4UQ2WLPRC40; ODFL: same-name record in US-DE vs SEC "VA" → flagged, not accepted) |
| FRED | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS` | Policy-rate context for floating-rate debt (0.08% Jan 2022 → 4.10% Dec 2022) |

Retrieved live on 2026-10-13 (UTC), stored content-addressed with sha256 in `data/source_snapshots/manifest.json`.
The application runs from this snapshot by default and labels it "stored snapshot"; live mode re-fetches. Live
re-verification: `tests/test_live_sources.py` — **4 passed** against the real endpoints (§10).

## 3. Yellow Corporation FY2022 — source-to-screen example

Full table: [`docs/evidence/yellow_source_to_screen.md`](evidence/yellow_source_to_screen.md), produced by
`python scripts/verify_source_to_screen.py` (exit code 0 = all checks pass). For each of revenue, operating income,
D&A, interest expense, net income, total debt, cash, operating cash flow and capex it checks: raw XBRL value =
DB value = API value; the same figure is printed in the 10-K text; accession = 0000950170-23-002332; and the
formatted value appears in the approved memo where the memo lists it. Result: **PASS** for all 9 facts.
Derived: EBITDA $341.2M (197.8 + 143.4), net debt $1,302.9M, net debt/EBITDA 3.82x, EBITDA/interest 2.09x,
free cash flow −$70.5M (121.3 − 191.8), EBITDA margin 6.5%.

The browser test (`e2e/test_ui_e2e.py`) additionally reads the rendered Financials cells
(`$5,244.7M`, `-$70.5M`, `$1,538.0M`) and checks that the downloaded memo's sha256 equals the one shown on screen.

## 4. Figures and calculations match their sources

* Formula unit tests (normal, zero/negative denominators, missing inputs, period mixing, reported-value precedence,
  half-up rounding, recomputation): `tests/test_metrics.py` — 7 passed.
* XBRL parsing (point-in-time, restatement detection, duration validation, composite tags, missing metrics,
  10-K vs 10-K/A): `tests/test_sec_parsing.py` — 4 passed.
* API values vs 10-K printed values: `test_yellow_facts_match_the_filing_text_and_api` — passed.
* Frontend rounding identical to backend: `src/test/format.test.ts` — passed.

## 5. Verified real deals vs illustrative records

| Deal | Classification | Notes |
|---|---|---|
| Yellow Corporation — FY2022 credit review | verified_real, historical | 48 facts, 7 documents, no missing metrics |
| Old Dominion Freight Line — FY2022 credit review | verified_real, historical | 44 facts; interest expense is not reported as an XBRL item → shown `n/a (missing)`, coverage not computed |
| Project Northwind (illustrative) | illustrative | fictional; kept as a demo of planted issues |
| Project Helios (illustrative) | illustrative | fictional; kept as a demo of payments/compliance issues |

Northwind and Helios were **not** renamed after real companies. They are labelled synthetic and separated.

## 6. UI screens and reports use validated data

Dashboard, deal list, deal header, Analysis, Financials, Sources & identity, Documents, Ask, IC memo and
Administration read only from the API, which reads the database populated by the ingestion pipeline.
No business values are hard-coded in the frontend application code (a `grep` of `frontend/src` outside `src/test/` for the Yellow figures returns nothing; the figures appear only in test fixtures). Error
and unavailable states: `n/a` values with reasons, empty states, explicit error boxes for failed source refresh,
incomplete runs and changed inputs. Screenshots: `docs/screenshots/`.

## 7. Visible login password removed

* `frontend/src/pages/Login.tsx` shows no password; input `type=password` by default with an eye toggle
  (`aria-label` "Show password"/"Hide password"). Demo chips fill the e-mail only and appear only when the
  server reports demo mode.
* a search for the old fixed password over `frontend/src`, `frontend/dist`, `backend/app`, `scripts`, `docs`: no matches
  (only this report and the baseline notes mention it).
* Tests: `src/test/login.test.tsx` (5 passed) and the browser test assert the password is not in the page.

## 8. Secure password handling and backend role enforcement

bcrypt cost 12; constant-time check for unknown users; generic error for unknown user, wrong password and locked
account; lockout after 5 failures; per-IP+email rate limit; password policy (≥12 chars, mixed case, digit,
symbol) for new users; httpOnly SameSite=Strict cookies; CSRF double-submit; 15-minute access tokens; single-use
rotating refresh tokens with reuse detection; logout revokes tokens server-side; validation errors never echo input;
passwords and tokens never logged (checked in `test_password_never_logged` and by grepping the e2e server log);
production config validation refuses demo mode, weak secrets, insecure cookies and http origins.
Tests: `tests/test_auth.py` — 13 passed; `tests/test_governance.py` — 8 passed (matrix, admin isolation,
non-member 404, analyst/admin cannot approve, segregation of duties, verified-deal upload block).

## 9. Audit history and approval-version controls

Hash-chained, append-only audit log (SQLite triggers; Postgres trigger variant in code), verify endpoint and CLI;
denials are audited. Approved memos are immutable `ReportVersion` rows (UPDATE/DELETE rejected by triggers), with
content and findings sha256; reviews are refused if inputs changed since the run; incomplete runs cannot be
approved. Tests: `test_audit_log_is_append_only_and_chain_verifies`,
`test_approval_rules_segregation_and_versioned_immutable_report`, `test_agent_failure_produces_incomplete_unapprovable_run`.
Backup → restore → `verify-audit` was exercised (chain valid after restore).

## 10. Test results (actual commands)

| Suite | Command | Result |
|---|---|---|
| Baseline (before) | `cd backend && python -m pytest -q` at `baseline-v1` | 26 passed |
| Backend (enterprise-v2) | `cd backend && python -m pytest -q` | 67 passed, 4 skipped |
| Backend (final remediation) | `cd backend && python -m pytest -q` | **106 passed, 4 skipped, exit 0** (the 4 live tests, skipped without `VANTAGE_LIVE_TESTS=1`) |
| Real-source integration | `VANTAGE_LIVE_TESTS=1 python -m pytest -q tests/test_live_sources.py` | **4 passed** (SEC companyfacts, SEC submissions, GLEIF, FRED) |
| Agent evaluation gate | `python ml/eval/run_eval.py` | **PASSED** — issue recall 1.00 (27 known issues), quality-gate rejection rate 0.00, 0 critical findings on the clean control and the held-out real case; [`eval_report.json`](evidence/eval_report.json) |
| Source-to-screen | `python scripts/verify_source_to_screen.py` | **PASS** — Yellow and Old Dominion, FY2019–22: 96/96 reported values printed in their own filing, 14 derived values recomputed |
| Frontend type-check | `cd frontend && npx tsc -b --noEmit` | passed, 0 errors |
| Frontend unit/UI | `cd frontend && npm test` | **12 passed** (4 files) |
| Frontend production build | `cd frontend && npm run build` | passed |
| Browser end-to-end | `pytest e2e` against a running server | **2 passed** (second flow: Old Dominion coverage, FCF exact inputs, LEI not accepted, rejection with required reason, run history). First flow: (login without visible password, eye toggle, analyst run on Yellow, findings/evidence, financial cells = 10-K values, sources/LEI, partner approval, memo download sha256 = on-screen sha256, admin audit chain verification, no console errors) |
| Lint | `ruff check backend ml scripts e2e --select E,F,I,B` | passed |

Mocked vs real: `test_sources_http.py` uses a mocked network (retries, 4xx, timeouts, snapshot tampering);
`test_live_sources.py` uses the real endpoints; all other tests use the committed real-source snapshot.

## 11. Remaining defects, unverified values and production-readiness gaps

* **Windows not executed.** Scripts (`scripts/windows/*.ps1`, `.cmd`) and a `windows-latest` CI job are provided
  but have not been run by me. Python 3.12 is untested (tested on 3.13).
* **Validation depth.** Two real companies only. Yellow's credit rules were written after reading its filing; only
  Old Dominion is held out. Rule-based extraction will miss differently worded disclosures; findings absent ≠ risk absent.
* **Adjusted EBITDA.** Covenants use lenders' adjusted EBITDA; the app compares unadjusted EBITDA and labels the
  finding as an approximation. Yellow's reported adjusted EBITDA ($343.1M in the 10-K table) is not parsed.
* **GLEIF.** Old Dominion's LEI is flagged (jurisdiction mismatch) and needs a human decision; there is no UI to
  accept it yet. Both LEIs show LAPSED registrations.
* **10-K/A.** Detected and disclosed, but amendment content is not parsed.
* **Scale.** Single-process design: the audit hash chain lock, run lock and rate limiter are in-process; use one
  worker. Multi-instance deployment would need DB-level locking (e.g. Postgres advisory locks) and a shared rate limiter.
* **Audit tamper-resistance** is tamper-*evident*: someone with direct database-file access could rewrite the whole
  chain. Shipping entries to WORM storage/SIEM is recommended.
* **No SSO/MFA**, no password reset flow, no user self-service; admin creates users via API/CLI.
* **LLM mode** (Claude/OpenAI) is implemented but was not exercised in these tests (offline mode only).
* **LoRA clause model** (0.79 macro-F1 on synthetic held-out templates) is not used for findings; it is not validated
  on real contracts.
* **Optional container files** in `deploy/optional-container` were not re-validated.
* No load testing, penetration test, accessibility audit or compliance certification has been done. The system is
  **production-oriented, not production-ready/certified.**

## 12. Windows startup (exact commands)

```powershell
# Prerequisites: Python 3.13 (python.org, "Add to PATH"), Node.js 20/22. In the repository folder:
powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1
#   -> creates .venv, installs backend\requirements-dev.txt, writes .env (prints the demo password once),
#      runs npm ci + npm run build, applies migrations, checks config
powershell -ExecutionPolicy Bypass -File scripts\windows\start.ps1
#   -> http://127.0.0.1:8000  (or: scripts\windows\start.cmd from cmd.exe)
powershell -ExecutionPolicy Bypass -File scripts\windows\test.ps1          # all automated checks
powershell -ExecutionPolicy Bypass -File scripts\windows\dev.ps1           # hot-reload API + Vite dev server
```

Manual equivalents: `py -3 -m venv .venv` · `.venv\Scripts\python -m pip install -r backend\requirements-dev.txt` ·
`.venv\Scripts\python scripts\manage.py setup` · `cd frontend; npm ci; npm run build; cd ..` ·
`.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000`.
If you already have a `vantage.db` from an earlier version, do **not** reset it. Inspect it read-only with
`.venv\Scripts\python scripts\manage.py inspect-db --path backend\vantage.db` and follow "Upgrading an existing
database" in OPERATIONS.md (start on a new database file, or rehearse the migration on a copy).

**Superseded:** the final remediation results are in [FINAL_AUDIT_REPORT.md](FINAL_AUDIT_REPORT.md).
