"""Positive evidence for the credit thesis, derived only from stored facts and the same methodology thresholds the
risk rules use. A strength is listed only when its fact exists; nothing is inferred from missing data.
Strengths do not change the risk score — they balance the memo so a reader sees both sides."""
from __future__ import annotations

from app.analytics.metrics import fmt
from app.tools.credit import INTEREST_COVER_LOW, NET_LEVERAGE_HIGH

THIN_MARGIN_PCT = 8.0


def strengths(facts: dict[tuple[str, int], dict], year: int | None) -> list[dict]:
    if year is None:
        return []

    def f(m, y=year):
        v = facts.get((m, y))
        return v if v and v.get("value") is not None else None

    out: list[dict] = []

    def add(key, text, *refs):
        out.append({"key": key, "text": text, "facts": [{"metric": r["metric"], "fiscal_year": r["fiscal_year"],
                                                         "value": r["value"], "unit": r["unit"]} for r in refs]})

    nd, lev = f("net_debt"), f("net_leverage_x")
    if nd and nd["value"] < 0:
        add("net_cash", f"Net cash position of {fmt(-nd['value'], nd['unit'])} at FY{year} year end (cash exceeds total debt).", nd)
    elif lev and lev["value"] < NET_LEVERAGE_HIGH:
        add("leverage", f"Net leverage (net debt / EBITDA) of {fmt(lev['value'], 'x')} is below the {NET_LEVERAGE_HIGH}x comfort level.", lev)
    cov = f("interest_coverage_x")
    if cov and cov["value"] >= INTEREST_COVER_LOW:
        add("coverage", f"EBITDA covers interest expense {fmt(cov['value'], 'x')} (comfort level {INTEREST_COVER_LOW}x).", cov)
    fcf = f("free_cash_flow")
    if fcf and fcf["value"] > 0:
        add("fcf", f"Positive free cash flow of {fmt(fcf['value'], fcf['unit'])} in FY{year}.", fcf)
    g = f("revenue_growth_pct")
    if g and g["value"] > 0:
        add("growth", f"Revenue grew {fmt(g['value'], 'pct')} in FY{year}.", g)
    m = f("ebitda_margin_pct")
    if m and m["value"] >= THIN_MARGIN_PCT:
        add("margin", f"EBITDA margin of {fmt(m['value'], 'pct')} (above the {THIN_MARGIN_PCT:g}% thin-margin threshold).", m)
    ni = f("net_income")
    if ni and ni["value"] > 0:
        add("profit", f"Net income of {fmt(ni['value'], ni['unit'])} in FY{year}.", ni)
    cr = f("current_ratio_x")
    if cr and cr["value"] >= 1.0:
        add("current_ratio", f"Current ratio of {fmt(cr['value'], 'x')} (current assets exceed current liabilities).", cr)
    return out
