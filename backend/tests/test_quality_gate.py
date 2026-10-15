"""The quality gate must check that evidence SUPPORTS a claim, not merely that a citation exists."""
import math

from app.agents.evidence import (
    DealContext,
    Doc,
    Hit,
    ev_assumption,
    ev_excerpt,
    finding,
)
from app.agents.quality import run_quality_gate, score, verify_finding

TEXT = "The Term Loan has a maturity date of June 30, 2024, with a single payment due at maturity."
DOC = Doc("d1", "notes.txt", "financial_notes", TEXT, "https://sec.example/10k.htm", "0001", "2022-12-31", "verified_real")


def ctx():
    lev = {"id": "f1", "metric": "net_leverage_x", "fiscal_year": 2022, "value": 3.819, "unit": "x", "kind": "calculated",
           "formula": "net_debt / ebitda", "inputs": [{"metric": "net_debt", "fiscal_year": 2022, "value": 1302.9},
                                                      {"metric": "ebitda", "fiscal_year": 2022, "value": 341.2}],
           "period_end": "2022-12-31"}
    nd = {"id": "f2", "metric": "net_debt", "fiscal_year": 2022, "value": 1302.9, "unit": "USD_millions", "kind": "calculated",
          "formula": "", "inputs": [], "period_end": None}
    eb = {"id": "f3", "metric": "ebitda", "fiscal_year": 2022, "value": 341.2, "unit": "USD_millions", "kind": "calculated",
          "formula": "", "inputs": [], "period_end": None}
    return DealContext({"id": "x"}, [DOC], {("net_leverage_x", 2022): lev, ("net_debt", 2022): nd, ("ebitda", 2022): eb})


def lev_ev(value=3.819):
    return {"kind": "calculation", "fact_id": "f1", "metric": "net_leverage_x", "fiscal_year": 2022, "value": value,
            "unit": "x", "display": "3.82x", "formula": "net_debt / ebitda",
            "inputs": [{"metric": "net_debt", "fiscal_year": 2022, "value": 1302.9},
                       {"metric": "ebitda", "fiscal_year": 2022, "value": 341.2}]}


def lev_finding(detail="Net debt / EBITDA of 3.82x exceeds the 3.5x comfort level.", ev=None, threshold=3.5):
    return finding("FIN.LEVERAGE_HIGH", "t", "financial", "high", "calculation", "Leverage above credit comfort level",
                   detail, ev or [lev_ev(), ev_assumption("comfort", threshold, "convention")])


def test_valid_calculation_is_verified():
    assert verify_finding(lev_finding(), ctx())[0] == "verified"


def test_condition_must_hold_on_evidence_values():
    status, notes = verify_finding(lev_finding(detail="Net debt / EBITDA of 3.82x exceeds the 4.0x comfort level.",
                                               threshold=4.0), ctx())
    assert status == "rejected" and "condition" in notes[-1]


def test_number_not_in_evidence_is_rejected():
    status, notes = verify_finding(lev_finding(detail="Net debt / EBITDA of 4.75x exceeds the 3.5x comfort level."), ctx())
    assert status == "rejected" and "4.75" in notes[-1]


def test_value_that_differs_from_stored_fact_is_rejected():
    status, notes = verify_finding(lev_finding(ev=[lev_ev(9.9), ev_assumption("c", 3.5, "x")]), ctx())
    assert status == "rejected"


def test_invented_excerpt_is_rejected():
    fake = {"kind": "document_excerpt", "document_id": "d1", "filename": "notes.txt", "excerpt": "We will default in 2023.",
            "locator": {"start": 0, "end": 24}}
    f = finding("FIN.CANNOT_REPAY_IF_ACCELERATED", "t", "financial", "high", "source_fact", "Cannot repay",
                "The company says it cannot repay.", [fake])
    status, notes = verify_finding(f, ctx())
    assert status == "rejected" and "locator" in notes[0]


def test_real_excerpt_without_required_support_is_rejected():
    hit = Hit(DOC, None, 0, len(TEXT))
    f = finding("FIN.CANNOT_REPAY_IF_ACCELERATED", "t", "financial", "high", "source_fact", "Cannot repay",
                "The company says it cannot repay.", [ev_excerpt(hit)])
    status, notes = verify_finding(f, ctx())
    assert status == "rejected" and "support" in notes[-1]


def test_interpretation_with_verified_evidence_is_supported_not_verified():
    hit = Hit(DOC, None, 0, len(TEXT))
    f = finding("RED.X", "t", "consistency", "high", "interpretation", "Refinancing not discussed",
                "Maturities are near but no plan is described.", [ev_excerpt(hit)])
    assert verify_finding(f, ctx())[0] == "supported"


def test_score_components_sum_to_overall_and_are_bounded():
    fs = [{"severity": s, "category": c, "verification_status": v} for s, c, v in
          [("critical", "financial", "verified"), ("high", "esg", "verified"), ("medium", "consistency", "supported"),
           ("low", "market", "verified")]]
    overall, comps, rec = score(fs)
    total = 25 + 12 + 5 * 0.75 + 1
    assert overall == round(100 * (1 - math.exp(-total / 130)), 1)
    assert round(sum(comps.values()), 1) == overall
    assert 0 <= overall < 100 and overall == 27.5 and rec == "Proceed"
    assert score([])[0] == 0.0 and score([])[2] == "Proceed"


def test_score_is_monotonic_in_findings():
    base = [{"severity": "high", "category": "financial", "verification_status": "verified"}]
    assert score(base * 2)[0] > score(base)[0]


def test_agent_failure_makes_run_incomplete():
    res = run_quality_gate([lev_finding()], ctx(), [{"agent": "legal_counsel", "error": "boom"}])
    assert res["incomplete"] and res["risk_score"] is None and "Incomplete" in res["recommendation"]


# ---------------------------------------------------------------- historical cut-off (look-ahead control)
def _cutoff_ctx(doc_filed: str, fact_filed: str):
    from datetime import date
    c = ctx()
    late_doc = Doc("d2", "later.txt", "financial_notes", TEXT, "https://sec.example/later.htm", "0002", "2023-12-31",
                   "verified_real", doc_filed)
    c.docs = [late_doc]
    c.facts[("cash", 2022)] = {"id": "f9", "metric": "cash", "fiscal_year": 2022, "value": 1.5, "unit": "USD_millions",
                               "kind": "reported", "filed": fact_filed}
    c.cutoff = date(2023, 2, 9)
    return c, late_doc


def test_document_filed_after_cutoff_is_rejected():
    c, d = _cutoff_ctx("2024-02-01", "2023-02-09")
    m = Hit(d, None, 0, len(TEXT))
    f = finding("FIN.MATURITY_WALL", "t", "financial", "high", "source_fact", "Maturity", "Term loan matures.",
                [ev_excerpt(m)])
    status, notes = verify_finding(f, c)
    assert status == "rejected" and any("look-ahead" in n for n in notes)


def test_document_filed_on_cutoff_is_allowed():
    c, d = _cutoff_ctx("2023-02-09", "2023-02-09")
    f = finding("FIN.MATURITY_WALL", "t", "financial", "high", "source_fact", "Maturity", "Term loan matures.",
                [ev_excerpt(Hit(d, None, 0, len(TEXT)))])
    assert not any("look-ahead" in n for n in verify_finding(f, c)[1])


def test_fact_and_macro_after_cutoff_are_removed():
    c, _ = _cutoff_ctx("2023-02-09", "2023-03-16")     # e.g. a value from the 10-K/A filed after the 10-K
    fact_ev = {"kind": "reported_fact", "fact_id": "f9", "metric": "cash", "fiscal_year": 2022, "value": 1.5,
               "unit": "USD_millions", "display": "$1.5M"}
    macro = {"kind": "macro_series", "series_id": "FEDFUNDS", "observations": [{"date": "2023-03-01", "value": 4.65}]}
    f = finding("FIN.X", "t", "financial", "low", "source_fact", "Cash", "Cash was low.", [fact_ev, macro])
    status, notes = verify_finding(f, c)
    assert status == "rejected" and sum("look-ahead" in n for n in notes) == 2
