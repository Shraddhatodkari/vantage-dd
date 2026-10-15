"""Release 1.2 data-coverage fixes found by the blind benchmark, and the going-concern rule.

* total debt: the most inclusive complete XBRL aggregate is used (Saia tags LongTermDebt = 0 while carrying
  $31.0M of finance-lease debt; first-tag-wins gave $0.0)
* receivables / cash: standard alternative tags (Diebold Nixdorf); a combined cash line is labelled as such
* going concern: only affirmative statements count, never hypothetical risk-factor wording"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest
from app.agents.nodes import GOING_CONCERN
from app.sources import sec

SNAP = Path(__file__).resolve().parents[2] / "data" / "source_snapshots" / "sec_companyfacts"


def _facts(cik: str, fy: int, filed: str) -> dict:
    cf = json.loads(next(SNAP.glob(f"*CIK{int(cik):010d}.json")).read_text(encoding="utf-8"))
    ends = [date(fy - k, 12, 31) for k in range(3, -1, -1)]
    return {(f["metric"], f["fiscal_year"]): f for f in sec.extract_annual_facts(cf, ends, date.fromisoformat(filed))}


def test_total_debt_uses_the_most_inclusive_aggregate():
    saia = _facts("1177702", 2022, "2023-02-23")
    d = saia[("total_debt", 2022)]
    assert d["value"] == pytest.approx(31.0, abs=0.05)          # 16.5 noncurrent + 14.5 current (finance leases)
    assert "LongTermDebtAndCapitalLeaseObligations" in d["xbrl_tag"]
    assert saia[("total_debt", 2021)]["value"] == pytest.approx(50.4, abs=0.05)


def test_already_verified_debt_figures_are_unchanged():
    assert _facts("716006", 2022, "2023-02-09")[("total_debt", 2022)]["value"] == pytest.approx(1538.0, abs=0.05)
    assert _facts("878927", 2022, "2023-02-22")[("total_debt", 2022)]["value"] == pytest.approx(100.0, abs=0.05)


def test_alternative_standard_tags_and_labelled_cash_fallback():
    dbd = _facts("28823", 2022, "2023-03-16")
    assert dbd[("receivables", 2022)]["value"] == pytest.approx(612.2, abs=0.05)
    assert dbd[("total_debt", 2022)]["value"] == pytest.approx(2609.8, abs=0.05)   # 2,585.8 long-term + 24.0 notes payable
    cash = dbd[("cash", 2022)]
    assert cash["value"] == pytest.approx(319.1, abs=0.05) and "restricted cash" in cash["status_reason"]
    assert dbd[("capex", 2022)]["status"] == "missing"            # not tagged by the filer: n/a, never guessed
    # a company that reports unrestricted cash keeps it (no note)
    y = _facts("716006", 2022, "2023-02-09")[("cash", 2022)]
    assert y["value"] == pytest.approx(235.1, abs=0.05) and not y["status_reason"]


@pytest.mark.parametrize("text,fires", [
    ("These conditions raise substantial doubt about its ability to continue as a going concern.", True),
    ("These factors raise substantial doubt about the Company’s ability to continue as a going concern.", True),
    ("Accordingly, there is substantial doubt about our ability to continue as a going concern.", True),
    ("Failure to refinance could raise substantial doubt about our ability to continue as a going concern.", False),
    ("These events may raise substantial doubt about the Company's ability to continue as a going concern.", False),
    ("management must evaluate whether there are conditions or events, considered in the aggregate, that raise "
     "substantial doubt about the Company’s ability to continue as a going concern", False),
])
def test_going_concern_only_matches_affirmative_statements(text, fires):
    assert bool(re.search(GOING_CONCERN, text, re.I)) is fires


@pytest.mark.parametrize("text", [
    "These conditions would not raise substantial doubt about our ability to continue as a going concern.",
    "Such matters, if unresolved, raise substantial doubt about the Company's ability to continue as a going concern.",
    "These conditions will raise substantial doubt about our ability to continue as a going concern unless refinanced.",
])
def test_going_concern_ignores_conditional_wording(text):
    assert not re.search(GOING_CONCERN, text, re.I)


def test_negative_ebitda_with_debt_is_flagged_not_skipped(analyst):
    """Release 1.2: when EBITDA <= 0 the leverage ratio is 'n/a'; that must raise a finding, never silently pass."""
    from .conftest import deal_by, wait_run
    d = deal_by(analyst, "Diebold")
    run = wait_run(analyst, analyst.post(f"/api/v1/deals/{d['id']}/runs", json={}).json()["id"])
    codes = {f["code"]: f for f in run["findings"] if f["verification_status"] != "rejected"}
    neg = codes["FIN.NEGATIVE_EBITDA_WITH_DEBT"]
    assert neg["severity"] == "critical" and neg["verification_status"] == "verified"
    gc = codes["FIN.GOING_CONCERN"]
    assert gc["severity"] == "critical" and "substantial doubt" in gc["evidence"][0]["excerpt"]
    assert "FIN.LEVERAGE_HIGH" not in codes                       # the ratio itself is n/a, never 0
    cov = codes["FIN.COVERAGE_WEAK"]                              # negative EBITDA: plain wording, not "covers -0.91x"
    assert cov["verification_status"] == "verified" and cov["title"] == "Interest not covered by EBITDA"
    assert "covered none of the" in cov["detail"] and "covers interest expense -" not in cov["detail"]
    saia = deal_by(analyst, "Saia")
    run = wait_run(analyst, analyst.post(f"/api/v1/deals/{saia['id']}/runs", json={}).json()["id"])
    assert not {"FIN.NEGATIVE_EBITDA_WITH_DEBT", "FIN.GOING_CONCERN"} & {f["code"] for f in run["findings"]}
