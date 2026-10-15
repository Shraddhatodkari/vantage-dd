"""Credit and capital-structure tools: standard credit-analysis checks a lender or restructuring
adviser runs on every borrower. Added after the real-filing test (Yellow Corp, FY2022 10-K) showed
the first version, tuned only on synthetic data rooms, missed refinancing and liquidity risk.
"""
from __future__ import annotations

import re
from datetime import date, datetime

# Widely used credit-analysis comfort levels (rating-agency style heuristics, not covenants).
NET_LEVERAGE_HIGH, NET_LEVERAGE_CRITICAL = 3.5, 5.0
INTEREST_COVER_LOW, INTEREST_COVER_CRITICAL = 2.5, 1.5

_DATE = r"((?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4})"
_MATURITY = re.compile(r"matur\w*(?: date\w*)?(?: of| on| is)?\s+" + _DATE, re.I)
_MIN_EBITDA = re.compile(r"minimum [^.]{0,80}?EBITDA of \$(\d+(?:\.\d+)?) million", re.I)


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%B %d, %Y").date()


def months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def find_maturities(text: str, as_of: date) -> list[dict]:
    """Every dated maturity mentioned in the text, with months remaining from the balance-sheet date."""
    out, seen = [], set()
    for m in _MATURITY.finditer(text):
        d = parse_date(m.group(1))
        if d in seen or d <= as_of:
            continue
        seen.add(d)
        out.append({"maturity": d.isoformat(), "months_from_balance_sheet": months_between(as_of, d)})
    return sorted(out, key=lambda x: x["maturity"])


def min_ebitda_covenant(text: str) -> float | None:
    m = _MIN_EBITDA.search(text)
    return float(m.group(1)) if m else None


def loss_years(fin: dict[int, dict[str, float]]) -> list[int]:
    return [y for y, f in fin.items() if f.get("net_income_musd", 0) < 0]
