import pytest
from app.analytics.financials import FinancialsError, parse_financials_csv


def test_blank_cells_are_missing_not_zero():
    rows = parse_financials_csv("fiscal_year,revenue_musd,cash_musd\n2024,100,\n", "f.csv")
    cash = next(r for r in rows if r["metric"] == "cash")
    assert cash["value"] is None and cash["status"] == "missing"


@pytest.mark.parametrize("text,msg", [
    ("year,revenue_musd\n2024,1\n", "fiscal_year"),
    ("fiscal_year,revenue_musd,ebitda\n2024,1,2\n", "Unknown CSV columns"),
    ("fiscal_year,revenue_musd\n2024,1\n2024,2\n", "duplicate"),
    ("fiscal_year,revenue_musd\n2024,abc\n", "not a number"),
    ("fiscal_year,revenue_musd\nFY24,1\n", "invalid fiscal_year"),
])
def test_invalid_csv_rejected(text, msg):
    with pytest.raises(FinancialsError, match=msg):
        parse_financials_csv(text, "f.csv")
