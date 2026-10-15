"""Fact-to-filing reconciliation: every reported FY2019-FY2022 value for Yellow and Old Dominion must be printed
(after its line-item label) in the 10-K it came from. Uses the sha256-verified stored snapshots (offline)."""
from __future__ import annotations

from datetime import date

import pytest
from app.sources import reconcile, sec
from app.sources.filing_text import html_to_text


def test_formats_and_labels():
    text = "Net cash provided by operating activities 1,691,582 1,215,365 and other 999"
    assert reconcile.find_in_text(1_691_582_000, text, "operating_cash_flow").startswith("thousands")
    assert reconcile.find_in_text(1_691_583_000, text, "operating_cash_flow")          # ±1 thousand rounding
    assert reconcile.find_in_text(1_691_582_000, text, "capex") is None                # wrong label -> no evidence
    assert reconcile.find_in_text(1_791_582_000, text, "operating_cash_flow") is None
    assert reconcile.find_in_text(-53_500_000, "Net loss $ (53.5)", "net_income").startswith("millions (1 dp)")
    assert reconcile.find_in_text(11_691_582_000, "operating activities 11,691,582", "operating_cash_flow")
    assert reconcile.find_in_text(691_582_000, "operating activities 1,691,582", "operating_cash_flow") is None


def test_check_fact_statuses():
    assert reconcile.check_fact(None, "x", "t").status == "not_checked"
    assert reconcile.check_fact(1.0, "x", None).status == "document_unavailable"
    assert reconcile.check_fact(123.4, "us-gaap:A + us-gaap:B", "debt 1").status == "composite"
    assert reconcile.check_fact(123.4, "us-gaap:A", "debt 1").status == "not_found"


@pytest.fixture(scope="module")
def facts_and_texts():
    out = []
    for cik in ("716006", "878927"):
        subs = sec.get_submissions(cik, "snapshot").json()
        cf = sec.get_companyfacts(cik, "snapshot").json()
        rep = sec.find_annual_report(subs, 2022)
        texts: dict[str, str] = {}
        for f in sec.extract_annual_facts(cf, [date(y, 12, 31) for y in (2019, 2020, 2021, 2022)], rep.filing_date):
            if f["status"] != "ok":
                continue
            if f["accession"] not in texts:
                doc = sec.get_filing_document(sec.filing_for_accession(subs, f["accession"]), "snapshot")
                texts[f["accession"]] = html_to_text(doc.text())
            out.append((cik, f, texts[f["accession"]]))
    return out


def test_every_reported_value_is_printed_in_its_own_filing(facts_and_texts):
    misses = [(c, f["metric"], f["fiscal_year"]) for c, f, t in facts_and_texts
              if reconcile.check_fact(f["value"], f["xbrl_tag"], t, f["metric"]).status != "matched"]
    assert len(facts_and_texts) == 96 and misses == []


def test_coincidental_match_rate_is_low(facts_and_texts):
    tot = fp = 0
    for _, f, t in facts_and_texts:
        base = {v[0] for v in reconcile._variants(f["value"] * 1e6)}
        for k in (1.013, 0.981, 1.07, 1.031, 0.95):
            if {v[0] for v in reconcile._variants(f["value"] * k * 1e6)} & base:
                continue
            tot += 1
            fp += reconcile.find_in_text(f["value"] * k * 1e6, t, f["metric"]) is not None
    assert tot > 400 and fp / tot < 0.02, (fp, tot)     # measured 3/480 (0.62%) on 2026-10-14


def test_odfl_fcf_inputs_reconcile_to_the_10k(facts_and_texts):
    """Regression for the FCF question: OCF 1,691,582 and capex 775,148 (thousands) are both printed in ODFL's
    FY2022 10-K; FCF = 916.434 -> $916.4M. The on-screen 1,691.6 - 775.1 = 916.5 is display rounding only."""
    from app.analytics.metrics import fmt, rnd
    f = {(fa["metric"], fa["fiscal_year"]): fa for c, fa, _ in facts_and_texts if c == "878927"}
    ocf, capex = f[("operating_cash_flow", 2022)]["value"], f[("capex", 2022)]["value"]
    assert ocf == pytest.approx(1691.582) and capex == pytest.approx(775.148)
    assert f[("capex", 2022)]["xbrl_tag"] == "us-gaap:PaymentsToAcquireProductiveAssets"
    assert rnd(ocf - capex, "USD_millions") == 916.4 and fmt(ocf - capex, "USD_millions") == "$916.4M"
    assert rnd(ocf, "USD_millions") - rnd(capex, "USD_millions") == pytest.approx(916.5)   # the independent-rounding artefact itself
