# Final enterprise readiness audit and remediation — report

Date: 14 October 2026. Scope: phases 1–8 of the "Final Enterprise Readiness Audit and Remediation" brief.
All work was done on a separate copy of the repository and on **temporary databases only**. Your files
`backend\vantage.db`, `backend\vantage-backup-20261013-215032.db` and `backend\vantage_migration_test.db` were
**never opened, read, migrated or modified**: they are on your computer and were not available in my workspace.
`reset-dev` was not run against any of your data.

**Verdict: internal pilot candidate.** This is not a production-ready system (see section 7 for the reasons and the
go-live checklist). It is also more than a local demo: every figure is traceable to its filing, and the
controls are enforced server-side and covered by tests.

---

## 1. Baseline (phase 1)

Starting point: tag `enterprise-v2` (commit `1eaaa75`). Backend 67 passed / 4 skipped; live sources 4 passed;
frontend 9 passed; browser e2e 1 passed; eval gate passed; Yellow source-to-screen 9/9. Details are in
[`evidence/00_baseline.md`](evidence/00_baseline.md).

## 2. Defects found and what happened to each

| # | Severity | Defect | Status | Fix and proof |
|---|---|---|---|---|
| D0 | **High** | **ODFL interest expense shown as "n/a" in every year, although the 10-K prints it.** ODFL tags the line `us-gaap:InterestAndDebtExpense`, which the extractor did not search. Found while checking the 10-K text for this report. | **Fixed** | Tag added as the last candidate. FY2019–22 = $0.377M / $2.782M / $1.727M / $1.563M, each found in its own filing. EBITDA/interest FY2022 = 1,354.24x. Regression test: `test_e2e_api.py::test_healthy_real_peer_scores_low` |
| D1 | High | FCF looked inconsistent: $916.4M shown, but the displayed 1,691.6 − 775.1 = 916.5 | **Fixed (display only — the calculation was correct)** | Stored values: 1,691.582 − 775.148 = 916.434 → $916.4M. Rounding each figure separately caused the 0.1 gap. The UI and evidence now show exact inputs and explain the rounding. Both inputs are printed in the 10-K ("1,691,582", "775,148"). Tests: `test_reconciliation.py::test_odfl_fcf_inputs_reconcile_to_the_10k`, `review.test.tsx` |
| D2 | High | Specialists did not disclose what they examined; zero documents looked the same as a clean result | **Fixed** | Each specialist writes a coverage record (documents, facts, rules, matches, findings, LLM status), stored per run. A coverage panel appears in the UI and a coverage table in the memo. The red team raises `RED.COVERAGE_GAP.*`; the gate re-counts documents independently. Tests: `test_lifecycle_security.py::test_coverage_is_recorded_and_disclosed`, e2e test 2 |
| D3 | Medium | ODFL "Cash balance declining" was rated medium with no context (net cash, FCF +$916.4M) | **Fixed** | Rated low when the company is net cash with positive FCF, with the context and the reason for the lower rating stated. Otherwise the rule is unchanged |
| D4 | High | No check that each reported fact appears in the filing it came from (FY2019–21 used other 10-Ks) | **Fixed** | `app/sources/reconcile.py`: each value is searched for in its own filing's text, after its line-item label. **96/96 reported values match** (Yellow 48, ODFL 48). Coincidental-match rate measured on perturbed values: 3/480 (0.62%). Per-fact status is stored and shown |
| D5 | Medium | Values revised before the cutoff were not disclosed | **Fixed** | `revision_note` is recorded when a later filing before the cutoff changed a value. No such revisions exist for these two companies (checked) |
| D6 | High | Historical cutoff was implicit and not enforced | **Fixed** | `deal.historical_cutoff` = 10-K filing date (Yellow 2023-02-09, ODFL 2023-02-22). The quality gate removes any document, fact, calculation input or FRED observation dated after it. Macro data is loaded only up to the cutoff. Tests: 3 look-ahead tests in `test_quality_gate.py` |
| D7 | Medium | Rejection did not require a reason | **Fixed** | API returns 422 without a reason (≥ 10 characters). The UI disables Reject until one is entered. The reason is audited and shown to the analyst. Tests: API, UI and e2e |
| D8 | High | Two simultaneous approvals → database IntegrityError (500) | **Fixed** | Atomic compare-and-set claim on the run status: exactly one approval succeeds, the other gets 409. A claim interrupted by a crash is released at restart. Test: `test_concurrent_approvals_produce_exactly_one_approval` |
| D9 | Medium | Source "freshness" mixed filing age with retrieval age | **Fixed** | Labels are now "Stored snapshot — not re-checked since retrieval" / "Retrieved live" and "retrieved N days ago"; the filing date is shown separately. The memo uses the same wording |
| D10 | High | LLM Q&A answers were not validated | **Fixed** | `app/agents/qa.py`: an answer must cite provided passages, every sentence with a figure must carry a citation, and every figure must appear in the cited passage. Otherwise the answer is withheld (reason shown) and extractive passages are returned; abstention is allowed. Tests with a mocked LLM: `test_llm_safety.py` |
| D11 | Low | No analysis history in the UI | **Fixed** | Run history strip (version, status, score, date). e2e test 2 |
| D12 | **High** | **Database safety:** (a) a refused legacy DB was still modified on open (WAL pragma); (b) API start-up and `setup.ps1` would upgrade an existing DB; (c) backup zips contained `-wal`/`-shm` files; (d) restore left the old WAL beside the restored DB, which SQLite could replay; (e) `reset-dev` deleted data | **Fixed** | (a) Read-only inspection before any engine connection, and the file is byte-identical afterwards. (b) Start-up refuses pending migrations unless `VANTAGE_AUTO_MIGRATE=true`; `setup.ps1` uses `migrate --new-only`; explicit `migrate` writes a backup first. (c, d) Single-file backups; sidecars are moved aside on restore. (e) `reset-dev` moves data aside and never deletes. New `inspect-db` (read-only) and `doctor`. Tests: `test_migrations.py` (3), `test_backup_restore.py` (5) |
| D13 | Medium | LLM used/failed status was not recorded | **Fixed** | Recorded per workstream and per run (`metrics.llm_status`). A failed LLM degrades to rules with the same result and is disclosed. Provider error messages are no longer logged (they may echo deal content) |
| D14 | Medium | Missing tests (expired token, 429, safe 500, non-member run/report access, backup/restore, migration with data, look-ahead, malformed LLM) | **Fixed** | 39 new backend tests, 3 new frontend tests, 1 new browser e2e |
| D15 | Medium | "Proceed" could be read as a guarantee | **Fixed** | A disclaimer appears under the score and in the memo |
| D16 | Low | Missing-dependency diagnosis (your environment lacked `langgraph-checkpoint-sqlite`) | **Fixed** | `python scripts/manage.py doctor` |
| U1 | — | GLEIF LEI `5299009TWK32WE417T96` for ODFL: same legal name, but GLEIF says US-DE and SEC says VA | **Unresolved by design** | Not auto-accepted. Shown as a candidate needing manual verification (e2e asserts this). There is no UI to accept it after human review yet |
| U2 | — | Market workstream has no documents for 10-K deals | **Disclosed, not fixable from filings alone** | Shown as a medium coverage-gap finding. An industry study would need to be added to the data room |
| B1 | — | Windows execution | **Blocked (no Windows machine here)** | Scripts and a `windows-latest` CI job exist; not run by me |
| B2 | — | Real LLM quality | **Blocked (no API key used)** | Only the safety logic is tested, with a mocked model |

## 3. Reconciliation: Old Dominion and Yellow (FY2022 as of each 10-K)

Full FY2019–FY2022 tables: [`evidence/odfl_source_to_screen.md`](evidence/odfl_source_to_screen.md) and
[`evidence/yellow_source_to_screen.md`](evidence/yellow_source_to_screen.md). For every fact the chain checked is:
XBRL snapshot → its own filing's text → database → API → screen display → approved memo.

| FY2022 ($M) | Old Dominion (10-K 0000950170-23-003783, filed 2023-02-22) | Yellow (10-K 0000950170-23-002332, filed 2023-02-09) |
|---|---|---|
| Revenue | 6,260.077 → $6,260.1M | 5,244.7 → $5,244.7M |
| Operating income | 1,840.632 | 197.8 |
| D&A | 276.050 | 143.4 |
| Interest expense | 1.563 (InterestAndDebtExpense) | 162.9 |
| Net income | 1,377.159 | 21.8 |
| Total debt | 99.963 → $100.0M | 1,538.0 |
| Cash | 186.312 | 235.1 |
| Operating cash flow | 1,691.582 | 121.3 |
| Capex | 775.148 (PaymentsToAcquireProductiveAssets) | 191.8 |
| **Free cash flow** | **916.434 → $916.4M** | **−70.5** |
| EBITDA | 2,116.682 | 341.2 |
| Net debt / EBITDA | −0.04x (net cash $86.3M) | 3.82x |
| EBITDA / interest | 1,354.24x | 2.09x |
| Reported values reconciled to their filing | 48 / 48 | 48 / 48 |
| Risk score (offline rules, risk-v3) | **5.2 → Proceed** (coverage gap 3.7 + financial 1.5) | **71.8 → Renegotiate price and terms** |
| GLEIF | Jurisdiction mismatch — **not accepted** | Exact match `529900SEX4UQ2WLPRC40` |

Yellow's score moved from 70.7 to 71.8 and ODFL's from 4.5 to 5.2. The only cause in both cases is the new
coverage-gap finding for the market workstream. No financial figure changed except ODFL interest expense (D0).

## 4. Live data vs stored snapshots

* All screens, the memo and the verification above use **stored snapshots** (`data/source_snapshots`,
  sha256-verified), labelled as such everywhere. They are never presented as live.
* Live retrievals made during this work (14 Oct 2026, through SEC/GLEIF/FRED):
  * the five comparative-year 10-Ks used for reconciliation (Yellow FY2020 and FY2021; ODFL FY2019–FY2021);
  * the four live integration tests. SEC companyfacts, SEC submissions and FRED were byte-identical to the stored
    copies. GLEIF's Yellow response differed only in `meta.goldenCopy.publishDate`.
* FRED observations are the current vintage, not as-published at the cutoff. FEDFUNDS is rarely revised;
  this is listed as a limitation.

## 5. Tests (exact commands, exit codes and counts)

| Suite | Command | Result | Data |
|---|---|---|---|
| Lint | `ruff check backend ml scripts e2e --select E,F,I,B --ignore E501,B008` | exit 0 | — |
| Backend | `cd backend && python -m pytest -q` | **106 passed, 4 skipped, exit 0** ([log](evidence/test_backend.txt)) | stored snapshots; network mocked in `test_sources_http.py`; LLM mocked in `test_llm_safety.py` |
| Live sources | `VANTAGE_LIVE_TESTS=1 python -m pytest -q tests/test_live_sources.py` | **4 passed, exit 0** ([log](evidence/test_live_sources.txt)) | **live** SEC, GLEIF, FRED |
| Source-to-screen | `python scripts/verify_source_to_screen.py` | **PASS both companies, exit 0** — 96/96 reported values, 14 derived values recomputed | stored snapshots, temporary DB |
| Agent eval gate | `python ml/eval/run_eval.py` | **PASSED, exit 0** ([report](evidence/eval_report.json)) | snapshots + synthetic cases |
| Frontend | `cd frontend && npx tsc --noEmit -p . && npx vitest run` | tsc exit 0; **12 passed, exit 0** ([log](evidence/test_frontend.txt)) | component tests, API mocked |
| Production build | `cd frontend && npm run build` | exit 0 | — |
| Browser e2e | `pytest e2e -v` against a running server on a temporary DB | **2 passed, exit 0** ([log](evidence/test_e2e_browser.txt)) — Yellow approval and memo hash; ODFL coverage, FCF exact inputs, capex reconciliation, LEI not accepted, rejection requiring a reason, run history | stored snapshots, offline rules |
| Log hygiene | grep of the e2e server log for the demo password and JWTs | 0 occurrences | — |

The 4 skipped backend tests are the live tests, which run only with `VANTAGE_LIVE_TESTS=1`. No test was deleted.
Two existing tests were changed: they encoded old behaviour and now assert the corrected behaviour with the same
intent. The duplicate-review test now sends a reason; the "missing is never zero" test now uses a value that really
is missing.

## 6. Changed files

Backend: `agents/{evidence,llm,nodes,quality,report,service,state}.py`, new `agents/qa.py`,
`api/{routes_deals,schemas}.py`, `core/config.py`, `db/{models,seed}.py`, `main.py`,
`sources/{real_deals,sec}.py`, new `sources/reconcile.py`, new migration
`0002_coverage_cutoff_reconciliation.py`.
Tests: new `test_migrations.py`, `test_backup_restore.py`, `test_reconciliation.py`,
`test_lifecycle_security.py`, `test_llm_safety.py`; extended `test_quality_gate.py`; adjusted
`test_governance.py` and `test_e2e_api.py` (see above).
Frontend: `pages/DealDetail.tsx`, `components/Evidence.tsx`, `lib/api.ts`, new `test/review.test.tsx`.
Scripts: `manage.py` (inspect-db, doctor, migrate --new-only, safe backup/restore/reset-dev),
`verify_source_to_screen.py` (both companies, all years), `windows/setup.ps1`. E2E: `e2e/test_ui_e2e.py`.
Data: 5 new SEC filing documents in `data/source_snapshots/sec_filing/`, 1 new GLEIF response, updated
manifest. Docs: this report, README, METHODOLOGY, OPERATIONS, ACCEPTANCE_REPORT, CAREER_GUIDE, evidence files,
screenshots 01–13.

## 7. Go-live checklist

Done and tested:

* [x] Server-side permission matrix, deal membership (404 for non-members, including runs and reports), segregation of duties
* [x] Cookie sessions, CSRF, refresh rotation, revocation, lockout, login rate limit (429), safe 500s
* [x] Immutable approved reports, hash-chained audit log, rejection reasons, single approval under concurrency
* [x] Migrations with pre-migration backup; start-up never upgrades or alters an existing DB; read-only inspection
* [x] Backup/restore with checksums (tamper rejected), tested end to end
* [x] Facts reconciled to filing text; historical cutoff enforced; coverage disclosed; LLM outputs validated

Still needed before production:

* [ ] **Run on your Windows PC** (`setup.ps1`, `start.ps1`, `test.ps1`) and keep the logs
* [ ] **Upgrade test on a copy of your migration-managed database first.** A `vantage.db` without migration
  history (the legacy file you described) is refused and left unchanged. Point `VANTAGE_DATABASE_URL` to a new file (see OPERATIONS)
* [ ] SSO/MFA, password reset, user self-service
* [ ] Multi-process safety: the audit-chain lock and rate limiter are in-process. Run 1 worker, or move to Postgres
  advisory locks and a shared limiter
* [ ] Ship audit entries to WORM/SIEM storage (the chain is tamper-evident, not tamper-proof against file access)
* [ ] UI for a human to accept or reject a flagged LEI (U1)
* [ ] Real-LLM evaluation with an API key; a blind validation set (companies that defaulted vs matched controls)
* [ ] Load test, penetration test, accessibility audit, data-protection review
* [ ] Scheduled backups and restore drills (Task Scheduler), plus monitoring of `/healthz`, `/readyz`, `/metrics`

**Verdict: internal pilot candidate.** It is suitable for a supervised internal pilot with named users on a single
Windows server, using historical public filings. It is not production-ready: the unchecked items above are
required, and its rules have been validated on only two real companies.
