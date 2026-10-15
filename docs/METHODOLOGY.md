# Methodology (risk-v4 / metrics-v3)

## 1. Where every number comes from

| Kind | Meaning | Example | Shown as |
|---|---|---|---|
| Reported | Taken directly from a source | Revenue FY2022 = 5,244.7 (us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax, 10-K 0000950170-23-002332) | superscript **R**, XBRL tag + accession on click |
| Calculated | Deterministic formula on reported values | Free cash flow = operating cash flow − capex = 121.3 − 191.8 = −70.5 | superscript **C**, formula + inputs on click |
| Assumption | A methodology threshold, not a fact | Leverage comfort level 3.5x | "Assumption" evidence item |
| Interpretation | Analytical judgement resting on verified evidence | "Management discussion does not address refinancing" | claim type *Interpretation* |
| Illustrative | Synthetic demo data | Project Northwind figures | amber "Illustrative (synthetic)" badge |
| Unavailable | Not reported, or not meaningful | Revenue growth FY2019 (needs FY2018) | `n/a` with the reason — never 0 |

### SEC XBRL extraction rules (`app/sources/sec.py`)
* Only `10-K` / `10-K/A` facts, in USD, for the exact fiscal-year end date.
* Flows must cover 350–380 days (quarters are excluded); balances must be instants.
* **Point-in-time:** only facts filed on or before the analysed 10-K's filing date are used. Later restatements are
  detected and noted (`restated`, `restatement_note`) but not mixed in.
* Ordered tag candidates per metric (e.g. revenue: `Revenues` → `RevenueFromContractWithCustomerExcludingAssessedTax`
  → `…IncludingAssessedTax`). Total debt may be a documented sum of tags (e.g. non-current + current).
* **Total debt uses the most inclusive complete candidate** (the largest), not the first one found: filers use
  `LongTermDebt` with different scopes (Saia reports it as 0 while carrying $31.0M of finance-lease debt). For
  credit work the more inclusive measure is the conservative one.
* Cash prefers unrestricted `CashAndCashEquivalentsAtCarryingValue`; only when a filer reports nothing else is the
  combined cash-and-restricted-cash line used, and the value is then labelled "includes restricted cash".
* A value that is the sum of several tagged lines whose total is not printed is reconciled line by line and shown as
  **composite** (e.g. Diebold Nixdorf: long-term debt 2,585.8 + notes payable 24.0).
* Interest expense candidates include `InterestAndDebtExpense` (Old Dominion tags its "Interest expense" line this way).
* **Revisions before the cut-off:** if a later filing (still before the cut-off) changed a value, the latest value is
  used and `revision_note` records the original value and filing.
* **Reconciliation to the filing text** (`app/sources/reconcile.py`): each reported value is searched for in the text
  of the filing it came from, as thousands (±1), millions to 1 dp, or whole millions (≥ 1,000M only), and only counts
  if the metric's line-item label appears shortly before it. Status per fact: matched / not_found / composite /
  document_unavailable. Result for Yellow and ODFL FY2019–22: 96/96 matched. The coincidental-match rate measured on
  values perturbed by 1–7% is 3/480 (0.62%), so a "matched" status is strong but not absolute evidence.
* Values are stored unrounded (USD ÷ 1,000,000); display rounding is half-up (1 dp for money and %, 2 dp for ratios),
  identical in the API, UI and memo.

## 2. Formulas (`app/analytics/metrics.py`)

| Metric | Formula | Not meaningful when |
|---|---|---|
| EBITDA (if not reported) | operating income + depreciation & amortisation | — |
| Revenue growth % | (revenue[t] / revenue[t−1] − 1) × 100 | prior revenue ≤ 0 or missing |
| EBITDA / operating / net margin % | metric / revenue × 100 | revenue ≤ 0 |
| Net debt | total debt − cash | — |
| Net leverage | net debt / EBITDA | EBITDA ≤ 0 |
| Gross leverage | total debt / EBITDA | EBITDA ≤ 0 |
| EBITDA / interest | EBITDA / interest expense | interest ≤ 0 or not reported |
| Free cash flow | operating cash flow − capital expenditure (cash-flow statement) | either missing |
| DSO (days) | receivables / revenue × 365 | revenue ≤ 0 |
| Current ratio | current assets / current liabilities | liabilities ≤ 0 |
| Cash conversion | operating cash flow / net income | net income ≤ 0 |

Missing inputs give `status=missing`; bad denominators give `status=not_meaningful`; the value is `null`, never 0.
A reported value (e.g. EBITDA in an uploaded CSV) is never overwritten by a calculation. Growth metrics require the
immediately preceding fiscal year (no skipping periods). Tests: `backend/tests/test_metrics.py`.

**Definitions to keep in mind:** EBITDA here is unadjusted (operating income + D&A). Credit agreements usually test
an *adjusted* EBITDA; findings comparing the two are labelled *Interpretation* with that limitation. Total debt is
book value as tagged (for Yellow, `LongTermDebt` includes lease financing obligations).

## 3. Quality gate (`app/agents/quality.py`)

A finding is accepted only if:
1. its schema is valid and it has evidence;
2. every excerpt equals the stored document text at its character locator;
3. every fact or calculation matches the stored value, and calculations re-compute from their inputs;
4. rule-specific support text is present (e.g. a pension finding must quote "Critical and Declining");
5. the rule's condition holds on the evidence values (e.g. leverage really exceeds the stated threshold);
6. every number in the title and text appears in the evidence;
7. interpretations rest on at least one verified fact, calculation or excerpt;
8. **historical cut-off:** evidence filed, published or observed after the deal's cut-off (the 10-K filing date) is
   removed; a finding left without evidence is rejected;
9. coverage-gap claims are re-counted independently against the data room.

Outcomes: **verified** (source facts and calculations), **supported** (interpretations), **rejected** (excluded from
score and memo conclusions, listed with reasons). There are no confidence percentages.

## 4. Risk score

T = Σ over accepted findings of severity weight (low 1, medium 5, high 12, critical 25) × verification factor
(verified 1.0, supported interpretation 0.75).
**Score = 100 × (1 − e^(−T/130))**, rounded half-up to 1 dp. Bands: < 30 Proceed; < 55 Proceed with conditions;
< 75 Renegotiate price and terms; ≥ 75 Do not proceed without remediation.
Workstream components = score × (category T / total T); after rounding, the largest component absorbs the
rounding difference, so the components **sum exactly to the score**. Properties tested: bounded in [0, 100),
monotonic in findings, deterministic.

**Coverage (risk-v3):** every specialist records what it examined (documents, facts, rules, matches, findings,
LLM status). A workstream that reviewed nothing produces a medium `RED.COVERAGE_GAP` finding: its risks are
unassessed, not cleared. A workstream that reviewed documents but matched no rule is disclosed as a limitation
("absence of a match is not evidence of absence") without adding to the score. When the company is net cash with
positive free cash flow, a cash decline is rated low (with that context) instead of medium.

**The recommendation is not a guarantee.** "Proceed" means no verified finding crossed the thresholds over the
evidence reviewed.

**Change from risk-v1:** v1 multiplied severity by arbitrary per-rule "confidence" constants (0.75–0.95) and showed
them as percentages. v2 removes them; only the verification outcome affects the weight.

## 5. Limitations

* Rules follow common disclosure wording; an absent finding is not proof that a risk is absent.
* The Yellow rules (maturity wall, pension, labour, PIK, waiver, acceleration statement) were written after reading
  that filing. Old Dominion is the only held-out real case so far. A proper validation needs a held-out set of
  filings from companies that later defaulted and a matched set that did not.
* Thresholds marked "analyst convention" are assumptions of this methodology.
* FRED series are the current vintage, not the values as published at the cut-off.
* LLM answers in "Ask the documents" are shown only if every figure appears in a cited passage. Otherwise the
  answer is withheld and the extractive passages are shown.

## 6. Coverage by evidence category, score contributions, strengths, display precision (final build)

* **Evidence categories.** Each workstream lists the evidence it needs, with a status: *finding raised*,
  *reviewed — no rule triggered* (the material is present and the rules found no issue), *insufficient evidence*
  (no relevant material in the data room), or *not performed* (the agent failed). A **required** category that is
  missing becomes a medium `RED.COVERAGE_GAP` finding. The quality gate re-counts the documents independently.
  Other missing categories are disclosed as information requests and are not scored. The payments-sector compliance
  category applies only to payments / third-party-risk deals.
* **Score contribution per finding:** weight = severity weight × verification factor; points = score × weight ÷
  Σ weights. Points add up to the score (±0.1 per finding from rounding). Overlap is possible and disclosed: for
  example, a maturity wall and "no refinancing discussion" both contribute.
* **Credit thesis (strengths):** listed when a fact meets the same thresholds the risk rules use (net cash or
  leverage < 3.5x, EBITDA/interest ≥ 2.5x, positive FCF, positive growth, EBITDA margin ≥ 8%, positive net income,
  current ratio ≥ 1). Strengths never change the score.
* **Ratio display:** values ≥ 100x show whole numbers, 10–100x one decimal, below 10x two decimals. Backend, UI and
  memo use the same rule; exact values are in provenance.
* **Charts:** one measure per chart, no dual axes, missing values drawn as gaps (never 0), legend for 2+ series,
  tooltips with the exact value. The palette was checked for colour-vision-deficiency separation. Charts read the
  same API values as the tables.

## 7. Release 1.1 notes

* **Leverage (metrics-v3):** gross leverage = total debt / EBITDA and net leverage = (total debt − cash) / EBITDA are
  both computed and labelled explicitly. The 3.5x comfort threshold applies to **net** leverage. Yellow FY2022: gross
  4.51x, net 3.82x.
* **Time basis:** each source is labelled historical (filed on or before the cut-off), filtered to the cut-off (XBRL
  facts file, FRED), current metadata (GLEIF identity, SEC submissions index: never used in scoring) or after
  cut-off (excluded).

## 8. Release 1.2 notes (risk-v4)

* **Going concern (`FIN.GOING_CONCERN`, critical).** Raised only for an *affirmative* statement ("these conditions
  raise substantial doubt about the Company's ability to continue as a going concern", "there is substantial
  doubt …"). Hypothetical risk-factor wording ("could/may/would raise substantial doubt"), the accounting standard's
  own description ("evaluate whether there are conditions … that raise substantial doubt") and "alleviated" are
  ignored. Across all 20 stored 10-K filings it fires once: Diebold Nixdorf FY2022.
* **Negative EBITDA with debt (`FIN.NEGATIVE_EBITDA_WITH_DEBT`, critical).** When EBITDA ≤ 0 the leverage ratio is
  not meaningful (shown as n/a); with net debt outstanding this is the worst leverage case and is now a finding.
  Previously the leverage rule silently did not fire.
* Both rules were added after the blind benchmark exposed the gaps (see `docs/evidence/blind_benchmark.md`); they
  did not change any previously verified result (Yellow 71.8, Old Dominion 5.2, Northwind 92.3, Helios 88.9,
  Aurora 6.0). Diebold Nixdorf is therefore no longer a blind case.
