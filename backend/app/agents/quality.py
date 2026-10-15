"""Quality gate: re-verifies every candidate finding against the stored evidence before a human sees it.

Checks (all must pass for a finding to be accepted):
 1. Schema: severity, category, claim type and non-empty evidence.
 2. Excerpts: the excerpt must equal the stored document text at its locator (no invented quotes).
 3. Facts: a reported/calculated fact must exist in the database with the same value.
 4. Calculations: stored formula re-run on stored inputs must reproduce the value.
 5. Entailment: rule-specific support patterns must appear in the excerpts, and rule conditions
    (e.g. leverage > threshold) must hold on the evidence values — not just "a citation exists".
 6. Numbers: every number in the title/detail must be present in the evidence (or be a year).
 7. Interpretations need at least one verified fact, calculation or excerpt.
 8. Historical cut-off (look-ahead control): evidence filed, published or observed after the deal's cut-off
    (the 10-K filing date for historical cases) is removed; a finding left without evidence is rejected.

Outcome: verified (facts/calculations), supported (interpretations with verified evidence) or rejected.
Rejected findings are kept for transparency but excluded from the score and the memo's conclusions.
"""
from __future__ import annotations

import math
import re

from app.agents.evidence import DealContext
from app.analytics.metrics import DECIMALS, recompute, rnd

METHODOLOGY_VERSION = "risk-v4"   # v4: going-concern rule, negative-EBITDA-with-debt rule (v3: coverage gaps, look-ahead control)
SEVERITY_WEIGHT = {"low": 1.0, "medium": 5.0, "high": 12.0, "critical": 25.0}
STATUS_FACTOR = {"verified": 1.0, "supported": 0.75}
SCALE_K = 130.0
CATEGORIES = {"financial", "legal", "market", "esg", "compliance", "consistency", "operational"}
CLAIM_TYPES = {"source_fact", "calculation", "interpretation", "assumption"}
THRESHOLDS = [(30, "Proceed"), (55, "Proceed with conditions"), (75, "Renegotiate price and terms"),
              (101, "Do not proceed without remediation")]

# Rule-specific entailment: patterns that must appear in at least one verified excerpt.
SUPPORT = {
    "FIN.CANNOT_REPAY_IF_ACCELERATED": r"not have sufficient cash to repay",
    "FIN.GOING_CONCERN": r"substantial doubt[^.]{0,80}going concern",
    "FIN.PIK_INTEREST": r"paid-in-kind|paid in kind",
    "FIN.COVENANT_WAIVER_HISTORY": r"waiver",
    "FIN.MATURITY_WALL": r"matur",
    "FIN.MIN_EBITDA_COVENANT": r"EBITDA",
    "FIN.FLOATING_RATE_RISING": r"variable|floating|Eurodollar|SOFR|LIBOR",
    "ESG.PENSION_CRITICAL": r"Critical\s+and\s+Declining",
    "ESG.UNIONISED": r"workforce",
    "ESG.LABOUR_AGREEMENT_EXPIRY": r"bargaining|labor agreement",
    "ESG.MATERIAL_WEAKNESS": r"material weakness",
    "LEG.LITIGATION": r"million",
    "LEG.CUSTOMER_CONCENTRATION": r"accounted for \d+%",
    "CMP.PCI_LAPSED": r"Attestation of Compliance expired",
    "CMP.CHARGEBACKS": r"chargeback ratio",
    "RED.EMBEDDED_INSTRUCTIONS": r"NEUTRALISED_INSTRUCTION",
}
_NUM = re.compile(r"(?<![A-Za-z0-9.])-?\d+(?:,\d{3})*(?:\.\d+)?")


def _numbers(text: str) -> set[float]:
    out = set()
    for m in _NUM.findall(text or ""):
        try:
            out.add(float(m.replace(",", "")))
        except ValueError:
            pass
    return out


def _evidence_numbers(ev: list[dict]) -> set[float]:
    nums: set[float] = set()

    def add(v, unit=None):
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, (int, float)):
            nums.add(float(v))
            for d in (0, 1, 2):
                nums.add(round(float(v), d))
            if unit:
                r = rnd(float(v), unit)
                if r is not None:
                    nums.add(r)
        elif isinstance(v, list):
            for x in v:
                add(x, unit)
        elif isinstance(v, dict):
            for x in v.values():
                add(x, unit)
        elif isinstance(v, str):
            nums.update(_numbers(v))
    for e in ev:
        if e["kind"] == "document_excerpt":
            nums.update(_numbers(e.get("excerpt", "")))
        else:
            add(e.get("value"), e.get("unit"))
            add(e.get("inputs"))
            add(e.get("observations"))
            for k in ("display", "fiscal_year", "period_end"):
                if isinstance(e.get(k), str):
                    nums.update(_numbers(e[k]))
            if e.get("fiscal_year"):
                nums.add(float(e["fiscal_year"]))
    return nums


def _claim_numbers(text: str) -> set[float]:
    # ignore years and ISO-date parts; they are checked through period metadata
    text = re.sub(r"\b\d{4}-\d{2}(?:-\d{2})?\b", " ", text)
    text = re.sub(r"\bFY\d{4}\b", " ", text)
    return {n for n in _numbers(text) if not (1990 <= n <= 2100 and float(n).is_integer())}


def _close(a: float, b: float) -> bool:
    return abs(abs(a) - abs(b)) <= max(0.051, abs(b) * 0.001)


def _after_cutoff(e: dict, ctx: DealContext) -> str | None:
    """Return a reason when an evidence item post-dates the historical cut-off."""
    if ctx.cutoff is None:
        return None
    cut = ctx.cutoff.isoformat()
    k = e.get("kind")
    if k == "document_excerpt":
        filed = e.get("filed") or next((d.filed for d in ctx.docs if d.id == e.get("document_id")), None)
        if filed and filed > cut:
            return f"document filed {filed} after the cut-off {cut}"
    elif k == "reported_fact":
        stored = next((v for v in ctx.facts.values() if v["id"] == e.get("fact_id")), None)
        filed = (stored or {}).get("filed") or e.get("filed")
        if filed and filed > cut:
            return f"{e.get('metric')} FY{e.get('fiscal_year')} filed {filed} after the cut-off {cut}"
    elif k == "calculation":
        for inp in e.get("inputs") or []:
            src = ctx.facts.get((inp.get("metric"), inp.get("fiscal_year")))
            if src and src.get("filed") and src["filed"] > cut:
                return f"input {inp['metric']} FY{inp['fiscal_year']} filed {src['filed']} after the cut-off {cut}"
    elif k == "macro_series":
        late = [o["date"] for o in e.get("observations") or [] if o.get("date", "") > cut]
        if late:
            return f"{e.get('series_id')} observation(s) {late[:3]} after the cut-off {cut}"
    return None


def verify_finding(f: dict, ctx: DealContext) -> tuple[str, list[str]]:
    notes: list[str] = []
    if f.get("severity") not in SEVERITY_WEIGHT or f.get("category") not in CATEGORIES \
            or f.get("claim_type") not in CLAIM_TYPES or not f.get("title") or not f.get("detail"):
        return "rejected", ["schema: invalid severity, category, claim type or empty text"]
    ev = f.get("evidence") or []
    if not ev:
        return "rejected", ["no evidence"]
    docs = {d.id: d for d in ctx.docs}
    facts_by_id = {v["id"]: v for v in ctx.facts.values()}
    good: list[dict] = []
    for e in ev:
        k = e.get("kind")
        if (late := _after_cutoff(e, ctx)):
            notes.append(f"look-ahead: {late} — evidence removed")
            continue
        if k == "document_excerpt":
            d = docs.get(e.get("document_id"))
            loc = e.get("locator") or {}
            if not d or d.text[loc.get("start", 0):loc.get("end", -1)] != e.get("excerpt") or not e.get("excerpt"):
                notes.append(f"excerpt not found at its locator in '{e.get('filename')}' — rejected as unverifiable")
                continue
            good.append(e)
        elif k in ("reported_fact", "calculation") and e.get("fact_id"):
            db_f = facts_by_id.get(e["fact_id"])
            if not db_f or db_f["value"] is None or not _close(db_f["value"], e["value"]):
                notes.append(f"{e.get('metric')} FY{e.get('fiscal_year')}: value does not match the stored fact")
                continue
            if k == "calculation":
                rv = recompute({"metric": e["metric"], "inputs": e["inputs"]})
                if rv is None or not _close(rv, e["value"]):
                    notes.append(f"{e['metric']}: recomputation from inputs does not reproduce the value")
                    continue
                for inp in e["inputs"]:  # inputs must still match the stored facts
                    src = ctx.facts.get((inp["metric"], inp["fiscal_year"]))
                    if src is None or src["value"] is None or not _close(src["value"], inp["value"]):
                        notes.append(f"{e['metric']}: input {inp['metric']} FY{inp['fiscal_year']} differs from stored fact")
                        break
                else:
                    good.append(e)
                continue
            good.append(e)
        elif k in ("calculation", "assumption", "macro_series"):
            good.append(e)  # ad-hoc calculations are checked through numbers + rule conditions below
        else:
            notes.append(f"unknown evidence kind {k!r}")
    if not good:
        return "rejected", notes + ["no evidence survived verification"]
    if len(good) < len(ev):
        f["evidence"] = good
    pat = SUPPORT.get(f["code"]) or next((v for c, v in SUPPORT.items() if f["code"].startswith(c)), None)
    excerpts = " ".join(e["excerpt"] for e in good if e["kind"] == "document_excerpt")
    if pat and not re.search(pat, excerpts, re.I):
        return "rejected", notes + [f"evidence does not contain the required support ({pat})"]
    cond = _condition_ok(f, good, ctx)
    if cond is False:
        return "rejected", notes + ["rule condition does not hold on the evidence values"]
    missing = [n for n in _claim_numbers(f["title"] + " " + f["detail"])
               if not any(_close(n, s) for s in _evidence_numbers(good))]
    if missing:
        return "rejected", notes + [f"numbers not supported by evidence: {sorted(missing)[:5]}"]
    if f["claim_type"] in ("interpretation", "assumption"):
        return "supported", notes + ["interpretation supported by verified evidence"]
    return "verified", notes


def _val(ev: list[dict], metric: str) -> float | None:
    return next((e["value"] for e in ev if e.get("metric") == metric and isinstance(e.get("value"), (int, float))), None)


def _condition_ok(f: dict, ev: list[dict], ctx: DealContext | None = None) -> bool | None:
    code = f["code"]
    if code.startswith("RED.COVERAGE_GAP") and ctx is not None:
        # independent re-count: the claimed document count must equal the data room's actual count
        e = next((x for x in ev if x.get("metric") == "documents_reviewed"), None)
        if e is None:
            return False
        types = next((i.get("doc_types") for i in e.get("inputs") or [] if isinstance(i, dict)), None) or []
        actual = len(ctx.by_types(types)) if types else 0
        if code == "RED.COVERAGE_GAP.financial_analyst":
            actual = sum(1 for v in ctx.facts.values() if v.get("kind") == "reported" and v.get("value") is not None)
        return actual == e["value"] == 0
    a = next((e["value"] for e in ev if e["kind"] == "assumption"), None)
    if code == "FIN.LEVERAGE_HIGH":
        v = _val(ev, "net_leverage_x")
        return v is not None and a is not None and v > a
    if code == "FIN.COVERAGE_WEAK":
        v = _val(ev, "interest_coverage_x")
        return v is not None and a is not None and v < a
    if code == "FIN.NEGATIVE_FCF":
        v = _val(ev, "free_cash_flow")
        return v is not None and v < 0
    if code == "FIN.THIN_MARGIN":
        v = _val(ev, "ebitda_margin_pct")
        return v is not None and 0 < v < (a or 0)
    if code == "FIN.CASH_DECLINE":
        v = _val(ev, "cash_change_pct")
        return v is not None and v < -20
    if code == "FIN.RECURRING_LOSSES":
        return sum(1 for e in ev if e.get("metric") == "net_income" and e["value"] < 0) >= 2
    if code == "FIN.MATURITY_WALL":
        months = next((e["value"] for e in ev if e.get("metric") == "months_to_maturity"), None)
        return bool(months) and min(months) <= (a or 24)
    if code.startswith("FIN.COVENANT_BREACH"):
        return True if _val(ev, "net_leverage_x") or _val(ev, "interest_coverage_x") else False
    return None


def score(validated: list[dict]) -> tuple[float, dict[str, float], str]:
    """Overall = 100 * (1 - exp(-T / K)), T = Σ severity_weight × status_factor.
    Category components are the category's share of T applied to the overall score, so the components
    add up exactly to the overall score."""
    by_cat: dict[str, float] = {}
    for f in validated:
        w = SEVERITY_WEIGHT[f["severity"]] * STATUS_FACTOR[f["verification_status"]]
        by_cat[f["category"]] = by_cat.get(f["category"], 0.0) + w
    total = sum(by_cat.values())
    overall = round(100 * (1 - math.exp(-total / SCALE_K)), 1)
    comps = {k: round(overall * v / total, 1) for k, v in by_cat.items()} if total else {}
    if comps:  # make rounded components sum exactly to the rounded overall
        diff = round(overall - sum(comps.values()), 1)
        kmax = max(comps, key=comps.get)
        comps[kmax] = round(comps[kmax] + diff, 1)
    rec = next(label for limit, label in THRESHOLDS if overall < limit)
    return overall, comps, rec


def contributions(validated: list[dict], overall: float | None) -> dict[str, dict]:
    """Per-finding share of the score: weight_i = severity weight × verification factor; points_i = overall ×
    weight_i / Σ weights. Points add up to the overall score (up to rounding). Keyed by (code, title)."""
    ws = {(f["code"], f["title"]): SEVERITY_WEIGHT[f["severity"]] * STATUS_FACTOR[f["verification_status"]]
          for f in validated if f.get("verification_status") in STATUS_FACTOR}
    total = sum(ws.values())
    return {k: {"weight": w, "points": round((overall or 0) * w / total, 1) if total and overall is not None else None}
            for k, w in ws.items()}


def run_quality_gate(candidates: list[dict], ctx: DealContext, agent_errors: list[dict]) -> dict:
    validated, rejected, seen = [], [], set()
    for f in candidates:
        key = (f.get("code"), f.get("title", "").lower())
        if key in seen:
            continue
        seen.add(key)
        status, notes = verify_finding(f, ctx)
        f = {**f, "verification_status": status, "verification_notes": notes}
        (rejected if status == "rejected" else validated).append(f)
    overall, comps, rec = score(validated)
    incomplete = bool(agent_errors)
    return {"validated": validated, "rejected": rejected, "risk_score": None if incomplete else overall,
            "breakdown": comps, "recommendation": "Incomplete — not eligible for approval" if incomplete else rec,
            "incomplete": incomplete, "decimals": DECIMALS}
