# Blind benchmark — three more real companies (release 1.2)

Pre-registered in commit `48b5915` (`ml/eval/golden.json`) **before** any of these companies' data was loaded into
the application. Policy: report-only (not release-gating); rules frozen for the blind run. Outcomes happened after each
cut-off and are never shown to the application.

| Company | 10-K used (cut-off) | What happened later | Expected |
|---|---|---|---|
| Party City Holdco | FY2021 | Filed for Chapter 11 on 17 Jan 2023, about 11 months after the FY2021 10-K (filed 28 Feb 2022) | elevated |
| Diebold Nixdorf | FY2022 | Filed a prepackaged Chapter 11 on 1 Jun 2023, about 2.5 months after the FY2022 10-K (filed 16 Mar 2023) | elevated |
| Saia | FY2022 | No default; continued operating normally (healthy control) | low |

## Stage 1 — blind (code exactly as at the pre-registration commit)

| Company | Risk score | Recommendation | Critical | Expectation met |
|---|---|---|---|---|
| Party City Holdco | 58.4 | Renegotiate price and terms | 2 | yes |
| Diebold Nixdorf | 37.0 | Proceed with conditions | 1 | **no** |
| Saia | 4.5 | Proceed | 0 | yes |

**Blind result: 2 of 3.** Diebold Nixdorf was missed (37.0, 'Proceed with conditions').

Why Diebold was missed (diagnosed after the blind run):

1. **Data coverage:** 16 of 48 figures were missing because Diebold reports total debt, cash and receivables under standard
   XBRL tags the extractor did not list (`NotesPayableCurrent`, a combined cash line, `ReceivablesNetCurrent`), so leverage
   could not be computed. The same review found that Saia's total debt was extracted as **$0.0** (its `LongTermDebt` tag is
   0; its debt is finance leases) — a genuine extraction bug, flagged at the time by the filing-text check.
2. **Methodology gap:** the 10-K states that 'these conditions raise substantial doubt about [the Company's] ability to
   continue as a going concern'; there was no going-concern rule.
3. **Silent skip:** with EBITDA ≤ 0 the leverage ratio is 'not meaningful', and the leverage rule simply did not fire —
   treating the worst case as no finding.

Fixes (generic, with tests, applied to every company): most-inclusive total-debt aggregate; standard alternative tags
(combined cash line labelled 'includes restricted cash'); 'operating profit' label for reconciliation; going-concern
rule (affirmative statements only — hypothetical risk-factor wording is ignored); negative-EBITDA-with-debt rule.
Methodology version bumped to **risk-v4**. Diebold capex remains n/a: the filer does not tag it in XBRL.

## Stage 2 — after the fixes (Diebold is NO LONGER blind for these rules)

| Company | Risk score | Recommendation | Critical | Expectation met |
|---|---|---|---|---|
| Party City Holdco | 58.4 | Renegotiate price and terms | 2 | yes |
| Diebold Nixdorf | 60.9 | Renegotiate price and terms | 3 | yes |
| Saia | 4.5 | Proceed | 0 | yes |

The previously verified cases were unchanged by the fixes (Yellow 71.8, Old Dominion 5.2, Northwind 92.3, Helios 88.9,
Aurora 6.0). Party City and Saia remain blind results; Diebold's stage-2 result only shows the fixes work and must not
be read as predictive evidence. Five real companies are still far too few to validate scores as default predictors.

Data: 5 companies × 12 metrics × 4 years = 240 expected values; 236 reported (Diebold capex not tagged); 232 printed
in their own filing; Diebold's 4 total-debt values are the sum of two separately printed lines (status 'composite').
