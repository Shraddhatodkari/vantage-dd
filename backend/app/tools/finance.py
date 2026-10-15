"""Covenant testing helper (used by the MCP server). All other financial calculations live in
app/analytics/metrics.py, which records formulas and inputs for every derived value."""
from __future__ import annotations


def covenant_test(ratios: dict[str, float], max_net_leverage: float | None = None,
                  min_interest_coverage: float | None = None) -> list[dict]:
    results = []
    if max_net_leverage is not None and ratios.get("net_leverage_x") is not None:
        v = ratios["net_leverage_x"]
        results.append({"covenant": "max_net_leverage", "threshold": max_net_leverage, "actual": v,
                        "breach": v > max_net_leverage,
                        "headroom_pct": round((max_net_leverage - v) / max_net_leverage * 100, 1)})
    if min_interest_coverage is not None and ratios.get("interest_coverage_x") is not None:
        v = ratios["interest_coverage_x"]
        results.append({"covenant": "min_interest_coverage", "threshold": min_interest_coverage, "actual": v,
                        "breach": v < min_interest_coverage,
                        "headroom_pct": round((v - min_interest_coverage) / min_interest_coverage * 100, 1)})
    return results
