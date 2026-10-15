"""Financial formulas: normal, boundary and invalid inputs (pure unit tests, no I/O)."""
import pytest
from app.analytics.metrics import (
    BY_NAME,
    FactRef,
    compute_all,
    compute_metric,
    fmt,
    recompute,
    rnd,
)


def facts(**kw):
    out = {}
    for key, v in kw.items():
        metric, year = key.rsplit("_", 1)
        out[(metric, int(year))] = FactRef(metric, int(year), v, "USD_millions", {"src": "test"})
    return out


def test_yellow_style_ratios_match_hand_calculation():
    f = facts(revenue_2022=5244.7, revenue_2021=5121.8, operating_income_2022=197.8,
              depreciation_amortization_2022=143.4, interest_expense_2022=162.9, total_debt_2022=1538.0,
              cash_2022=235.1, operating_cash_flow_2022=121.3, capex_2022=191.8, net_income_2022=21.8)
    c = compute_all(f, [2021, 2022])
    assert c[("ebitda", 2022)].value == pytest.approx(341.2)
    assert rnd(c[("revenue_growth_pct", 2022)].value, "pct") == 2.4
    assert rnd(c[("ebitda_margin_pct", 2022)].value, "pct") == 6.5
    assert rnd(c[("net_leverage_x", 2022)].value, "x") == 3.82          # (1538.0-235.1)/341.2
    assert rnd(c[("interest_coverage_x", 2022)].value, "x") == 2.09     # 341.2/162.9
    assert c[("free_cash_flow", 2022)].value == pytest.approx(-70.5)    # OCF - capex, cash-flow statement
    assert c[("free_cash_flow", 2022)].inputs[0]["metric"] == "operating_cash_flow"


def test_zero_and_negative_denominators_are_not_meaningful_not_zero():
    f = facts(ebitda_2022=-5.0, net_debt_2022=100.0, interest_expense_2022=0.0, revenue_2022=0.0, net_income_2022=10.0)
    lev = compute_metric(BY_NAME["net_leverage_x"], f, 2022)
    cov = compute_metric(BY_NAME["interest_coverage_x"], f, 2022)
    mar = compute_metric(BY_NAME["net_margin_pct"], f, 2022)
    assert (lev.value, lev.status) == (None, "not_meaningful") and "EBITDA" in lev.reason
    assert (cov.value, cov.status) == (None, "not_meaningful")
    assert (mar.value, mar.status) == (None, "not_meaningful")


def test_missing_inputs_are_reported_never_imputed():
    c = compute_metric(BY_NAME["free_cash_flow"], facts(operating_cash_flow_2022=10.0), 2022)
    assert c.value is None and c.status == "missing" and "capex FY2022" in c.reason


def test_growth_requires_the_prior_period_and_never_mixes_years():
    c = compute_metric(BY_NAME["revenue_growth_pct"], facts(revenue_2022=110.0, revenue_2020=100.0), 2022)
    assert c.status == "missing" and "revenue FY2021" in c.reason


def test_reported_value_takes_precedence_over_calculation():
    f = facts(ebitda_2025=40.1, operating_income_2025=1.0, depreciation_amortization_2025=1.0, revenue_2025=308.8)
    c = compute_all(f, [2025])
    assert ("ebitda", 2025) not in c                      # not recalculated over the source value
    assert rnd(c[("ebitda_margin_pct", 2025)].value, "pct") == 13.0


def test_half_up_rounding_and_formatting():
    assert rnd(2.345, "x") == 2.35 and rnd(0.05, "pct") == 0.1
    assert fmt(-70.5, "USD_millions") == "-$70.5M" and fmt(None, "pct") == "n/a"
    assert fmt(5244.7, "USD_millions") == "$5,244.7M"


def test_recompute_reproduces_stored_calculation():
    c = compute_metric(BY_NAME["dso_days"], facts(receivables_2025=63.2, revenue_2025=308.8), 2025)
    assert recompute(c.to_dict()) == pytest.approx(c.value)
    tampered = c.to_dict()
    tampered["inputs"][0]["value"] = 70.0
    assert recompute(tampered) != pytest.approx(c.value)
