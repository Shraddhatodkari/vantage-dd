"""Deterministic financial metrics with full provenance.

Every derived value is a `Calc` carrying its formula, the exact input values (each with a reference to
the reported fact it came from) and a status. Missing inputs or non-meaningful denominators yield
value=None with status 'missing' / 'not_meaningful' — never zero, never an invented number.
Calculations use unrounded inputs; rounding (half-up) happens only for display via `fmt`.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from decimal import ROUND_HALF_UP, Decimal

METHODOLOGY_VERSION = "metrics-v3"   # v3: explicit gross leverage (total debt / EBITDA) beside net leverage
DECIMALS = {"USD_millions": 1, "pct": 1, "x": 2, "days": 1, "bps": 1, "USD_billions": 2}


@dataclass
class FactRef:
    metric: str
    fiscal_year: int
    value: float | None
    unit: str
    ref: dict = field(default_factory=dict)   # fact id / xbrl tag / accession / document


@dataclass
class Calc:
    metric: str
    fiscal_year: int
    value: float | None
    unit: str
    formula: str
    inputs: list[dict]
    status: str = "ok"              # ok | missing | not_meaningful
    reason: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def rnd(value: float | None, unit: str) -> float | None:
    if value is None:
        return None
    q = Decimal(1).scaleb(-DECIMALS.get(unit, 2))
    return float(Decimal(repr(value)).quantize(q, rounding=ROUND_HALF_UP))


def ratio_decimals(value: float) -> int:
    """Ratios carry fewer decimals as they grow: 2,844.53x implies a precision the inputs do not have."""
    a = abs(value)
    return 0 if a >= 100 else 1 if a >= 10 else 2


def fmt(value: float | None, unit: str) -> str:
    if value is None:
        return "n/a"
    if unit == "x":
        d = ratio_decimals(value)
        v = float(Decimal(repr(value)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))
        return f"{v:,.{d}f}x"
    v = rnd(value, unit)
    d = DECIMALS.get(unit, 2)
    if unit == "USD_millions":
        return f"-${abs(v):,.{d}f}M" if v < 0 else f"${v:,.{d}f}M"
    suffix = {"pct": "%", "x": "x", "days": " days", "bps": " bps"}.get(unit, "")
    return f"{v:,.{d}f}{suffix}"


Facts = dict[tuple[str, int], FactRef]


def _inp(f: FactRef) -> dict:
    return {"metric": f.metric, "fiscal_year": f.fiscal_year, "value": f.value, "unit": f.unit, "ref": f.ref}


@dataclass
class MetricDef:
    name: str
    unit: str
    formula: str
    needs: list[tuple[str, int]]     # (metric, year offset)
    fn: Callable[..., float]
    guard: Callable[..., str | None] | None = None   # returns a reason if not meaningful


def _pos(i: int, label: str):
    return lambda *v: None if v[i] > 0 else f"{label} is zero or negative ({v[i]})"


REGISTRY: list[MetricDef] = [
    MetricDef("ebitda", "USD_millions", "operating_income + depreciation_amortization",
              [("operating_income", 0), ("depreciation_amortization", 0)], lambda oi, da: oi + da),
    MetricDef("revenue_growth_pct", "pct", "(revenue[t] / revenue[t-1] - 1) * 100",
              [("revenue", 0), ("revenue", -1)], lambda r, p: (r / p - 1) * 100, _pos(1, "prior-year revenue")),
    MetricDef("ebitda_margin_pct", "pct", "ebitda / revenue * 100", [("ebitda", 0), ("revenue", 0)],
              lambda e, r: e / r * 100, _pos(1, "revenue")),
    MetricDef("operating_margin_pct", "pct", "operating_income / revenue * 100",
              [("operating_income", 0), ("revenue", 0)], lambda o, r: o / r * 100, _pos(1, "revenue")),
    MetricDef("net_margin_pct", "pct", "net_income / revenue * 100", [("net_income", 0), ("revenue", 0)],
              lambda n, r: n / r * 100, _pos(1, "revenue")),
    MetricDef("net_debt", "USD_millions", "total_debt - cash", [("total_debt", 0), ("cash", 0)], lambda d, c: d - c),
    MetricDef("net_leverage_x", "x", "net_debt / ebitda", [("net_debt", 0), ("ebitda", 0)], lambda nd, e: nd / e,
              _pos(1, "EBITDA")),
    MetricDef("gross_leverage_x", "x", "total_debt / ebitda", [("total_debt", 0), ("ebitda", 0)], lambda d, e: d / e,
              _pos(1, "EBITDA")),
    MetricDef("interest_coverage_x", "x", "ebitda / interest_expense", [("ebitda", 0), ("interest_expense", 0)],
              lambda e, i: e / i, _pos(1, "interest expense")),
    MetricDef("free_cash_flow", "USD_millions", "operating_cash_flow - capex (both from the cash-flow statement)",
              [("operating_cash_flow", 0), ("capex", 0)], lambda o, c: o - c),
    MetricDef("dso_days", "days", "receivables / revenue * 365", [("receivables", 0), ("revenue", 0)],
              lambda a, r: a / r * 365, _pos(1, "revenue")),
    MetricDef("current_ratio_x", "x", "current_assets / current_liabilities",
              [("current_assets", 0), ("current_liabilities", 0)], lambda a, b: a / b, _pos(1, "current liabilities")),
    MetricDef("cash_conversion_x", "x", "operating_cash_flow / net_income",
              [("operating_cash_flow", 0), ("net_income", 0)], lambda o, n: o / n, _pos(1, "net income")),
    MetricDef("receivables_growth_pct", "pct", "(receivables[t] / receivables[t-1] - 1) * 100",
              [("receivables", 0), ("receivables", -1)], lambda a, b: (a / b - 1) * 100, _pos(1, "prior receivables")),
    MetricDef("cash_change_pct", "pct", "(cash[t] / cash[t-1] - 1) * 100", [("cash", 0), ("cash", -1)],
              lambda a, b: (a / b - 1) * 100, _pos(1, "prior-year cash")),
]
BY_NAME = {m.name: m for m in REGISTRY}


def compute_metric(mdef: MetricDef, facts: Facts, year: int) -> Calc:
    refs = [facts.get((m, year + off)) for m, off in mdef.needs]
    inputs = [_inp(r) if r else {"metric": m, "fiscal_year": year + off, "value": None}
              for r, (m, off) in zip(refs, mdef.needs, strict=True)]
    missing = [f"{m} FY{year + off}" for r, (m, off) in zip(refs, mdef.needs, strict=True) if r is None or r.value is None]
    if missing:
        return Calc(mdef.name, year, None, mdef.unit, mdef.formula, inputs, "missing", "missing input: " + ", ".join(missing))
    vals = [r.value for r in refs]
    if mdef.guard and (why := mdef.guard(*vals)):
        return Calc(mdef.name, year, None, mdef.unit, mdef.formula, inputs, "not_meaningful", why)
    return Calc(mdef.name, year, mdef.fn(*vals), mdef.unit, mdef.formula, inputs)


def compute_all(reported: Facts, years: list[int]) -> dict[tuple[str, int], Calc]:
    """Compute every registry metric for every year. A reported EBITDA (e.g. in an illustrative CSV)
    takes precedence over the operating-income-based calculation and is labelled as reported."""
    facts: Facts = dict(reported)
    out: dict[tuple[str, int], Calc] = {}
    for y in sorted(years):
        for m in REGISTRY:
            if (m.name, y) in reported:      # reported value wins; do not overwrite a source fact
                continue
            c = compute_metric(m, facts, y)
            out[(m.name, y)] = c
            facts[(m.name, y)] = FactRef(m.name, y, c.value, m.unit, {"calculated": True, "formula": m.formula})
    return out


def recompute(calc: dict) -> float | None:
    """Re-run a stored calculation from its stored inputs (used by the quality gate)."""
    mdef = BY_NAME.get(calc["metric"])
    if mdef is None:
        return None
    vals = [i.get("value") for i in calc["inputs"]]
    if any(v is None for v in vals) or (mdef.guard and mdef.guard(*vals)):
        return None
    return mdef.fn(*vals)
