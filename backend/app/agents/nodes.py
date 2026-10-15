"""Agent nodes of the due-diligence graph.

Pattern for every specialist ("tools first, LLM second"):
  1. read authoritative inputs: FinancialFact rows (reported + calculated) and stored documents;
  2. apply deterministic rules, each producing a finding with a stable `code` and typed evidence;
  3. optionally ask an LLM for additional findings, which must quote the documents verbatim;
  4. hand everything to the quality gate, which re-verifies evidence before anything reaches a human.

Every node is wrapped by `safe_node`: an exception is recorded as an agent error and the run is marked
incomplete — it can never silently produce a report that looks complete.
"""
from __future__ import annotations

import functools
import re
import time
import traceback
from datetime import date

from langgraph.types import interrupt

from app.agents import prompts
from app.agents.evidence import (
    DealContext,
    Hit,
    ev_assumption,
    ev_count,
    ev_excerpt,
    ev_fact,
    ev_macro,
    find,
    find_all,
    finding,
    load_context,
)
from app.agents.llm import AgentPlan, LLMFindings, compact, structured_call_ex
from app.agents.quality import run_quality_gate
from app.agents.state import DDState
from app.analytics.metrics import fmt
from app.tools.clauses import CLAUSE_RULES, scan_clauses
from app.tools.credit import (
    INTEREST_COVER_CRITICAL,
    INTEREST_COVER_LOW,
    NET_LEVERAGE_CRITICAL,
    NET_LEVERAGE_HIGH,
    find_maturities,
    months_between,
    parse_date,
)

SPECIALISTS = ["financial_analyst", "legal_counsel", "market_strategist", "esg_compliance"]
_WORDNUM = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve".split())}


def _event(agent: str, message: str, t0: float, status: str = "ok") -> dict:
    return {"agent": agent, "message": message, "status": status, "latency_ms": int((time.perf_counter() - t0) * 1000)}


def safe_node(name: str):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(state: DDState) -> dict:
            t0 = time.perf_counter()
            try:
                return fn(state)
            except Exception as exc:  # noqa: BLE001 — isolate agent failures
                err = f"{type(exc).__name__}: {exc}"
                return {"agent_errors": [{"agent": name, "error": err[:500],
                                          "trace": traceback.format_exc(limit=3)[-1500:]}],
                        "coverage": [{"agent": name, "status": "failed", "documents_reviewed": 0, "document_names": [],
                                      "doc_types": [], "facts_used": 0, "rules_evaluated": 0, "rule_matches": 0,
                                      "candidate_findings": 0, "llm": "not_run",
                                      "limitation": "Agent failed; its workstream was not completed."}],
                        "events": [_event(name, f"Agent failed: {err[:200]}. Run will be marked incomplete.", t0, "error")]}
        return wrapper
    return deco


def _ctx(state: DDState) -> DealContext:
    return load_context(state["deal"]["id"])


# Evidence categories each workstream needs: (key, label, doc types searched, presence pattern, finding-code
# prefixes, required). "required" categories that are missing become a scored coverage-gap finding; others are
# disclosed as insufficient evidence / follow-up. Presence is checked in the stored documents, never assumed.
CATEGORY_SPEC: dict[str, list[tuple]] = {
    "financial_analyst": [
        ("financial_statements", "Reported financial statements", None, None,
         ("FIN.LEVERAGE", "FIN.COVERAGE", "FIN.RECURRING", "FIN.NET_LOSS", "FIN.THIN", "FIN.RECEIVABLES",
          "FIN.CASH_CONVERSION", "FIN.VALUATION", "FIN.CHARGEBACK"), True),
        ("debt_maturities", "Debt maturities and repayment capacity", ["financial_notes", "management", "legal", "risk_factors"],
         r"matur", ("FIN.MATURITY_WALL", "FIN.CANNOT_REPAY"), False),
        ("covenants", "Financial covenants", ["financial_notes", "management", "legal"], r"covenant",
         ("FIN.COVENANT", "FIN.MIN_EBITDA"), False),
        ("liquidity", "Liquidity and cash flow", ["management", "financial_notes"], r"liquidity|cash flows?",
         ("FIN.CASH_DECLINE", "FIN.NEGATIVE_FCF", "FIN.PIK", "FIN.FLOATING"), False),
    ],
    "legal_counsel": [
        ("litigation", "Litigation and contingencies", ["legal", "financial_notes"],
         r"litigation|legal proceedings|contingenc", ("LEG.LITIGATION", "LEG.ENVIRONMENTAL", "LEG.DATA"), False),
        ("debt_agreements", "Credit agreement / indenture full text", ["legal"], r"credit agreement|indenture",
         ("LEG.CLAUSE",), False),
        ("customer_contracts", "Material customer and supplier contracts", ["legal"], r"customer|supplier",
         ("LEG.CUSTOMER", "LEG.PAYMENT", "LEG.CLAUSE"), False),
    ],
    "market_strategist": [
        ("company_market_description", "Company's own market and competition description", ["business", "risk_factors"],
         r"compet", (), False),
        ("independent_market_study", "Independent market or industry study", ["market"], r"\w", ("MKT.",), True),
    ],
    "esg_compliance": [
        ("pension", "Pension obligations", ["esg", "compliance", "legal", "risk_factors", "financial_notes", "controls", "business"], r"pension", ("ESG.PENSION",), False),
        ("labour", "Labour relations", ["esg", "compliance", "legal", "risk_factors", "financial_notes", "controls", "business"], r"union|collective bargaining", ("ESG.UNIONISED", "ESG.LABOUR", "ESG.TURNOVER"), False),
        ("controls", "Internal control over financial reporting", ["controls", "esg", "compliance"], r"internal control",
         ("ESG.MATERIAL_WEAKNESS",), False),
        ("compliance", "Sector regulatory compliance reports (licences, PCI, KYC/AML, sanctions)", ["compliance"], r"\w", ("CMP.",), False),
    ],
}
CATEGORY_STATUS = {"risk_found": "finding(s) raised", "reviewed_no_risk": "reviewed — no rule triggered",
                   "insufficient_evidence": "insufficient evidence", "not_performed": "not performed"}


def _categories(agent: str, ctx: DealContext, findings: list[dict]) -> list[dict]:
    out = []
    d = ctx.deal or {}
    payments = d.get("deal_type") == "vendor_risk" or "pay" in (d.get("sector") or "").lower()
    for key, label, types, pattern, prefixes, required in CATEGORY_SPEC.get(agent, []):
        if key == "compliance" and not payments:
            continue   # payments-sector regulation (PCI, KYC/AML, licences) does not apply to other sectors
        hits = [f for f in findings if prefixes and f["code"].startswith(prefixes)]
        if types is None:   # fact-based category
            n = sum(1 for v in ctx.facts.values() if v.get("kind") == "reported" and v.get("value") is not None)
            present, basis = n > 0, f"{n} reported facts"
        else:
            docs = ctx.by_types(types)
            rel = [d for d in docs if re.search(pattern, d.text, re.I)]
            present = bool(rel)
            basis = (f"{len(rel)} of {len(docs)} document(s) of type {', '.join(types)} discuss it" if docs
                     else f"no documents of type {', '.join(types)}")
        status = "risk_found" if hits else "reviewed_no_risk" if present else "insufficient_evidence"
        out.append({"key": key, "label": label, "status": status, "required": required, "doc_types": types or [],
                    "basis": basis, "findings": len(hits)})
    return out


def _coverage(agent: str, doc_types: list[str], docs: list, *, facts_used: int = 0, calculated: int = 0, rules: int = 0, matches: int = 0,
              findings: int = 0, llm: str = "not_configured", categories: list[dict] | None = None) -> dict:
    """Structured record of what a specialist actually examined. Zero documents or zero facts is stated as a
    limitation — it is never presented as a clean result."""
    lim = []
    if not docs and doc_types:
        lim.append(f"No documents of type {', '.join(doc_types)} in the data room — this workstream could not be "
                   "performed on documents")
    elif docs and matches == 0:
        lim.append(f"{rules} rule(s) evaluated on {len(docs)} document(s) with no match; absence of a match is not "
                   "evidence that the risk is absent")
    if llm == "failed":
        lim.append("LLM review failed; deterministic rules only")
    missing = [c["label"] for c in categories or [] if c["status"] == "insufficient_evidence"]
    if missing:
        lim.append("insufficient evidence for: " + "; ".join(missing))
    return {"agent": agent, "status": "completed", "categories": categories or [], "doc_types": doc_types,
            "documents_reviewed": len(docs),
            "document_names": [d.filename for d in docs][:12], "facts_used": facts_used, "calculated_values": calculated, "rules_evaluated": rules,
            "rule_matches": matches, "candidate_findings": findings, "llm": llm, "limitation": "; ".join(lim) or None}


def _llm_extra(agent: str, categories: list[str], ctx: DealContext, state: DDState, candidates: list[dict],
               doc_types: list[str]) -> tuple[list[dict], str]:
    """Optional LLM pass. The LLM must return verbatim quotes; each quote is located in a stored document
    and becomes excerpt evidence. Quotes that cannot be found are kept as-is so the quality gate rejects them."""
    docs = ctx.by_types(doc_types)
    if not docs:
        return [], "no_documents"
    corpus = "\n\n".join(f"[{d.filename}]\n{d.text[:6000]}" for d in docs)[:18000]
    d = state["deal"]
    out, status = structured_call_ex(LLMFindings, prompts.SYSTEM_BASE.format(agent_name=agent), prompts.SPECIALIST_TASK.format(
        deal_name=d["name"], target=d["target_company"], deal_type=d["deal_type"], sector=d["sector"],
        question=state.get("question", ""), candidates=compact([{k: c[k] for k in ("severity", "title", "detail")}
                                                                 for c in candidates], 2500),
        documents=corpus, categories=", ".join(categories)))
    if out is None:
        return [], status
    existing = {c["title"].lower() for c in candidates}
    extra = []
    for f in out.findings:
        if f.title.lower() in existing:
            continue
        ev = []
        for q in f.quotes[:3]:
            hit = next((Hit(doc, None, i, i + len(q)) for doc in docs if (i := doc.text.find(q)) >= 0), None)
            ev.append(ev_excerpt(hit) if hit else {"kind": "document_excerpt", "excerpt": q, "document_id": None,
                                                   "filename": "unlocated", "locator": None})
        extra.append(finding(f"LLM.{agent.upper()}", agent, f.category, f.severity, "interpretation", f.title,
                             f.detail, ev, "AI interpretation generated by an LLM from quoted evidence."))
    return extra, status


# ----------------------------------------------------------------------------- supervisor
@safe_node("supervisor")
def supervisor(state: DDState) -> dict:
    t0 = time.perf_counter()
    ctx = _ctx(state)
    types = sorted({d.doc_type for d in ctx.docs})
    plan = ["financial_analyst"]
    if {"legal", "financial_notes"} & set(types):
        plan.append("legal_counsel")
    if {"market", "business", "risk_factors"} & set(types):
        plan.append("market_strategist")
    if {"esg", "compliance", "risk_factors", "financial_notes", "controls"} & set(types):
        plan.append("esg_compliance")
    llm_plan, _ = structured_call_ex(AgentPlan, "You plan due-diligence work.", prompts.SUPERVISOR_PLAN.format(
        specialists=SPECIALISTS, deal_type=state["deal"]["deal_type"], doc_types=types,
        question=state.get("question", "")))
    if llm_plan:
        plan = list(dict.fromkeys(["financial_analyst", *[s for s in llm_plan.specialists if s in SPECIALISTS]]))
    nfacts = sum(1 for f in ctx.facts.values() if f["kind"] == "reported" and f["value"] is not None)
    return {"plan": plan, "events": [_event("supervisor",
            f"Data room: {len(ctx.docs)} documents ({', '.join(types) or 'none'}), {nfacts} reported financial facts"
            f"{f' up to FY{ctx.latest_year}' if ctx.latest_year else ''}. Dispatching {len(plan)} specialists: "
            f"{', '.join(plan)}.", t0)]}


# ----------------------------------------------------------------------------- financial analyst
def _f(ctx: DealContext, metric: str, year: int | None) -> dict | None:
    return ctx.fact(metric, year)


@safe_node("financial_analyst")
def financial_analyst(state: DDState) -> dict:
    t0, agent = time.perf_counter(), "financial_analyst"
    ctx = _ctx(state)
    y = ctx.latest_year
    out: list[dict] = []
    if y is None:
        cov = _coverage(agent, [], [], llm="not_run")
        cov["limitation"] = "No reported financial facts available; ratio analysis not performed"
        return {"coverage": [cov], "events": [_event(agent, "No reported financial facts available; ratio analysis "
                                                            "not performed (reported as a limitation, not as zero).", t0)]}
    F = lambda m, yr=y: _f(ctx, m, yr)  # noqa: E731
    years = sorted({yr for (_, yr), f in ctx.facts.items() if f["kind"] == "reported" and f["value"] is not None})

    # profile
    nd = F("net_debt")
    lev_metric = (("net_debt", "net cash") if nd and nd["value"] < 0
                  else ("net_leverage_x", "net leverage (net debt/EBITDA)"))
    prof = [F(m) for m in ("revenue", "revenue_growth_pct", "ebitda_margin_pct", "gross_leverage_x", lev_metric[0],
                           "interest_coverage_x", "free_cash_flow")]
    parts = [f"{lbl} {fmt(abs(f['value']) if lbl == 'net cash' else f['value'], f['unit'])}" for lbl, f in zip(
        ["revenue", "revenue growth", "EBITDA margin", "gross leverage (total debt/EBITDA)", lev_metric[1],
         "EBITDA/interest", "free cash flow"], prof, strict=True) if f]
    if parts:
        out.append(finding("FIN.PROFILE", agent, "financial", "low", "calculation", f"FY{y} financial profile",
                           f"FY{y}: " + ", ".join(parts) + ".", [ev_fact(f) for f in prof if f]))

    # covenant tests from documents (maximum leverage ratio / minimum interest coverage)
    legal_docs = ctx.by_types(["legal", "financial_notes", "management"])
    lev_cov = find(legal_docs, r"Leverage Ratio[^.]{0,160}?exceed\s+(\d+\.\d+)\s+to\s+1")
    int_cov = find(legal_docs, r"Interest[^.]{0,160}?less than\s+(\d+\.\d+)\s+to\s+1")
    for hit, metric, name, breach_fn in [
        (lev_cov, "net_leverage_x", "net leverage", lambda a, t: a > t),
        (int_cov, "interest_coverage_x", "interest coverage", lambda a, t: a < t)]:
        f = F(metric)
        if not hit or not f:
            continue
        thr = float(hit.match.group(1))
        actual = f["value"]
        headroom = (thr - actual) / thr * 100 if metric == "net_leverage_x" else (actual - thr) / thr * 100
        ev = [ev_fact(f), ev_excerpt(hit)]
        if breach_fn(actual, thr):
            out.append(finding(f"FIN.COVENANT_BREACH.{metric}", agent, "financial", "critical", "calculation",
                               f"Covenant breach: {name}",
                               f"FY{y} {name} of {fmt(actual, 'x')} is outside the {thr:.2f}x covenant level in the "
                               "credit agreement; unless waived this is an Event of Default.", ev,
                               "Covenant definitions (e.g. adjusted EBITDA) may differ from the reported figures used here."))
        elif headroom < 20:
            out.append(finding(f"FIN.COVENANT_THIN.{metric}", agent, "financial", "high", "calculation",
                               f"Thin covenant headroom: {name}",
                               f"{name.capitalize()} of {fmt(actual, 'x')} vs the {thr:.2f}x covenant leaves "
                               f"{fmt(headroom, 'pct')} headroom.", ev + [ev_count("headroom_pct", headroom, "(actual - threshold) / threshold * 100"),
                                                     ev_assumption("headroom_alert_pct", 20, "analyst convention")]))
    has_cov = {"net_leverage_x": bool(lev_cov), "interest_coverage_x": bool(int_cov)}

    # comfort levels (explicit assumptions, not covenants)
    lev = F("net_leverage_x")
    if lev and lev["value"] > NET_LEVERAGE_HIGH and not has_cov["net_leverage_x"]:
        out.append(finding("FIN.LEVERAGE_HIGH", agent, "financial",
                           "critical" if lev["value"] > NET_LEVERAGE_CRITICAL else "high", "calculation",
                           "Net leverage above credit comfort level",
                           f"Net leverage (net debt / EBITDA) of {fmt(lev['value'], 'x')} in FY{y} exceeds the "
                           f"{NET_LEVERAGE_HIGH}x comfort level used in this methodology"
                           + (f"; gross leverage (total debt / EBITDA) is {fmt(F('gross_leverage_x')['value'], 'x')}."
                              if F("gross_leverage_x") else "."),
                           [ev_fact(lev)] + ([ev_fact(F("gross_leverage_x"))] if F("gross_leverage_x") else [])
                           + [ev_assumption("net_leverage_comfort_x", NET_LEVERAGE_HIGH,
                                            "analyst convention, not a covenant; applied to NET leverage")],
                           "EBITDA here is operating income + D&A (unadjusted); debt is book value incl. lease financing obligations."))
    # a ratio that is "not meaningful" because EBITDA <= 0 is the WORST leverage case, not an absent one
    eb, nd = F("ebitda"), F("net_debt")
    if (not lev or lev.get("value") is None) and eb and nd and eb["value"] <= 0 < nd["value"] \
            and not has_cov["net_leverage_x"]:
        out.append(finding("FIN.NEGATIVE_EBITDA_WITH_DEBT", agent, "financial", "critical", "calculation",
                           "Debt outstanding with negative EBITDA (leverage not meaningful)",
                           f"EBITDA was {fmt(eb['value'], eb['unit'])} in FY{y} while net debt was "
                           f"{fmt(nd['value'], nd['unit'])}: operating earnings do not cover any of the debt, so a "
                           "leverage multiple cannot be computed.",
                           [ev_fact(eb), ev_fact(nd)],
                           "EBITDA here is operating income + D&A (unadjusted); lenders' adjusted EBITDA may differ."))
    cov = F("interest_coverage_x")
    if cov and cov["value"] < INTEREST_COVER_LOW and not has_cov["interest_coverage_x"]:
        ie = F("interest_expense")
        if cov["value"] < 0 and eb and ie:
            # a negative multiple reads badly: say plainly that operating earnings covered none of the interest
            detail = (f"EBITDA was negative ({fmt(eb['value'], eb['unit'])}) in FY{y}, so operating earnings covered none "
                      f"of the {fmt(ie['value'], ie['unit'])} interest expense (ratio {fmt(cov['value'], 'x')}; comfort "
                      f"level {INTEREST_COVER_LOW}x).")
            ev = [ev_fact(cov), ev_fact(eb), ev_fact(ie)]
        else:
            detail = (f"EBITDA covers interest expense {fmt(cov['value'], 'x')} in FY{y}, below the "
                      f"{INTEREST_COVER_LOW}x comfort level used in this methodology.")
            ev = [ev_fact(cov)]
        out.append(finding("FIN.COVERAGE_WEAK", agent, "financial",
                           "critical" if cov["value"] < INTEREST_COVER_CRITICAL else "high", "calculation",
                           "Interest not covered by EBITDA" if cov["value"] < 0 else "Weak interest coverage", detail,
                           ev + [ev_assumption("interest_cover_comfort_x", INTEREST_COVER_LOW,
                                               "analyst convention, not a covenant")]))
    # losses
    losses = [F("net_income", yr) for yr in years if F("net_income", yr) and F("net_income", yr)["value"] < 0]
    if len(losses) >= 2:
        out.append(finding("FIN.RECURRING_LOSSES", agent, "financial", "high", "source_fact", "Recurring net losses",
                           f"Net loss reported in {len(losses)} of the {len(years)} fiscal years analysed "
                           f"({', '.join('FY' + str(f['fiscal_year']) for f in losses)}).",
                           [ev_fact(f) for f in losses] + [ev_count("loss_years", len(losses), "years with net income < 0"),
                                                           ev_count("years_analysed", len(years), "fiscal years with facts")]))
    ni = F("net_margin_pct")
    if ni and ni["value"] < 0:
        out.append(finding("FIN.NET_LOSS", agent, "financial", "high", "calculation", "Loss-making at the net income level",
                           f"Net margin of {fmt(ni['value'], 'pct')} in FY{y}.", [ev_fact(ni)]))
    # free cash flow from the cash-flow statement
    fcf, ocf, capex = F("free_cash_flow"), F("operating_cash_flow"), F("capex")
    if fcf and fcf["value"] < 0 and ocf and capex:
        out.append(finding("FIN.NEGATIVE_FCF", agent, "financial", "high", "calculation", "Negative free cash flow",
                           f"FY{y} free cash flow of {fmt(fcf['value'], 'USD_millions')}: operating cash flow of "
                           f"{fmt(ocf['value'], 'USD_millions')} did not cover capital expenditure of "
                           f"{fmt(capex['value'], 'USD_millions')}.", [ev_fact(fcf), ev_fact(ocf), ev_fact(capex)]))
    em = F("ebitda_margin_pct")
    if em and 0 < em["value"] < 8:
        out.append(finding("FIN.THIN_MARGIN", agent, "financial", "medium", "calculation", "Thin EBITDA margin",
                           f"EBITDA margin of {fmt(em['value'], 'pct')} in FY{y} leaves little buffer against cost increases.",
                           [ev_fact(em), ev_assumption("thin_margin_pct", 8, "analyst convention")]))
    cc = F("cash_change_pct")
    if cc and cc["value"] < -20:
        c0, c1 = F("cash", y - 1), F("cash")
        nd, fcf_ = F("net_debt"), F("free_cash_flow")
        base = (f"Cash fell {fmt(abs(cc['value']), 'pct')} from {fmt(c0['value'], 'USD_millions')} to "
                f"{fmt(c1['value'], 'USD_millions')} in FY{y}")
        ev = [ev_fact(cc), ev_fact(c0), ev_fact(c1)]
        if nd and nd["value"] < 0 and fcf_ and fcf_["value"] > 0:
            # context matters: a net-cash company with positive FCF that spent cash is not a liquidity warning
            out.append(finding("FIN.CASH_DECLINE", agent, "financial", "low", "calculation",
                               "Cash balance fell, but the company remains net cash with positive free cash flow",
                               base + f". The company still held net cash of {fmt(abs(nd['value']), 'USD_millions')} "
                               f"and generated free cash flow of {fmt(fcf_['value'], 'USD_millions')}, so the decline "
                               "reflects uses of cash (e.g. investment or shareholder returns) rather than a liquidity "
                               "shortfall. Confirm the uses of cash in the cash-flow statement.",
                               ev + [ev_fact(nd), ev_fact(fcf_)],
                               "Severity reduced from medium to low because of the net cash position and positive FCF."))
        else:
            out.append(finding("FIN.CASH_DECLINE", agent, "financial", "medium", "calculation", "Cash balance declining",
                               base + ".", ev))
    # quality of earnings
    rg, recg = F("revenue_growth_pct"), F("receivables_growth_pct")
    if rg and recg and recg["value"] > rg["value"] * 1.5 and recg["value"] - rg["value"] > 10:
        d1, d0 = F("dso_days"), F("dso_days", y - 1)
        ev = [ev_fact(rg), ev_fact(recg)] + [ev_fact(x) for x in (d0, d1) if x]
        out.append(finding("FIN.RECEIVABLES_OUTPACING", agent, "financial", "high", "calculation",
                           "Receivables growing far faster than revenue",
                           f"Receivables grew {fmt(recg['value'], 'pct')} vs revenue growth of {fmt(rg['value'], 'pct')}"
                           + (f"; DSO rose from {fmt(d0['value'], 'days')} to {fmt(d1['value'], 'days')}." if d0 and d1 else ".")
                           + " A quality-of-earnings red flag.", ev))
    if len(years) >= 2:
        o0, o1, n0, n1 = F("operating_cash_flow", years[0]), F("operating_cash_flow"), F("net_income", years[0]), F("net_income")
        if o0 and o1 and n0 and n1 and o1["value"] < o0["value"] and n0["value"] > 0 and n1["value"] >= 0.9 * n0["value"]:
            out.append(finding("FIN.CASH_CONVERSION_DECLINE", agent, "financial", "high", "source_fact",
                               "Earnings not converting to cash",
                               f"Operating cash flow fell from {fmt(o0['value'], 'USD_millions')} (FY{years[0]}) to "
                               f"{fmt(o1['value'], 'USD_millions')} (FY{y}) while net income was "
                               f"{fmt(n0['value'], 'USD_millions')} and {fmt(n1['value'], 'USD_millions')}.",
                               [ev_fact(o0), ev_fact(o1), ev_fact(n0), ev_fact(n1)]))
    out += _capital_structure(agent, ctx, y)
    # illustrative payments metrics
    cb0, cb1 = F("chargeback_ratio_pct", years[0]), F("chargeback_ratio_pct")
    if cb0 and cb1 and cb1["value"] > cb0["value"]:
        out.append(finding("FIN.CHARGEBACK_TREND", agent, "financial", "high", "source_fact",
                           "Deteriorating loss metrics in payments portfolio",
                           f"Chargeback ratio rose from {fmt(cb0['value'], 'pct')} (FY{years[0]}) to "
                           f"{fmt(cb1['value'], 'pct')} (FY{y}).", [ev_fact(cb0), ev_fact(cb1)]))
    # valuation from a market document's comparable multiples
    comps = find(ctx.by_types(["market"]), r"(\d+(?:\.\d+)?)x to (\d+(?:\.\d+)?)x EBITDA")
    e, nd = F("ebitda"), F("net_debt")
    if comps and e and e["value"] > 0 and nd:
        lo, hi = float(comps.match.group(1)), float(comps.match.group(2))
        ev_lo, ev_hi = e["value"] * lo, e["value"] * hi
        out.append(finding("FIN.VALUATION_RANGE", agent, "financial", "low", "calculation",
                           "Valuation range from transaction comparables",
                           f"{lo}x–{hi}x FY{y} EBITDA of {fmt(e['value'], 'USD_millions')} implies enterprise value "
                           f"{fmt(ev_lo, 'USD_millions')}–{fmt(ev_hi, 'USD_millions')}; less net debt of "
                           f"{fmt(nd['value'], 'USD_millions')} gives equity value {fmt(ev_lo - nd['value'], 'USD_millions')}–"
                           f"{fmt(ev_hi - nd['value'], 'USD_millions')}.",
                           [ev_fact(e), ev_fact(nd), ev_excerpt(comps),
                            {"kind": "calculation", "metric": "valuation_range", "formula": "ebitda * multiple; - net_debt",
                             "value": [ev_lo, ev_hi, ev_lo - nd["value"], ev_hi - nd["value"]], "unit": "USD_millions",
                             "inputs": [{"metric": "ebitda", "value": e["value"]}, {"metric": "multiple_low", "value": lo},
                                        {"metric": "multiple_high", "value": hi}, {"metric": "net_debt", "value": nd["value"]}]}],
                           "Multiples come from the market document; they are not independently verified."))
    extra, llm = _llm_extra(agent, ["financial"], ctx, state, out, ["management", "financial_notes"])
    out += extra
    # reported facts (from filings) and calculated values (formulas over them) are counted separately
    nf = sum(1 for f in ctx.facts.values() if f["value"] is not None and f["kind"] == "reported")
    nc = sum(1 for f in ctx.facts.values() if f["value"] is not None and f["kind"] == "calculated")
    fin_types = ["legal", "financial_notes", "management", "risk_factors", "market"]
    cov = _coverage(agent, fin_types, ctx.by_types(fin_types), facts_used=nf, calculated=nc, rules=FIN_RULES,
                    matches=sum(1 for f in out if f["code"] != "FIN.PROFILE"), findings=len(out), llm=llm,
                    categories=_categories(agent, ctx, out))
    return {"findings": out, "coverage": [cov],
            "events": [_event(agent, f"Used {len(years)} fiscal years of facts (FY{years[0]}–FY{y}); "
                                     f"produced {len(out)} candidate findings.", t0)]}


FIN_RULES = 18   # ratio, covenant, cash-flow, quality-of-earnings, valuation and capital-structure checks


def _capital_structure(agent: str, ctx: DealContext, y: int) -> list[dict]:
    out: list[dict] = []
    docs = ctx.by_types(["legal", "financial_notes", "management", "risk_factors"])
    as_of = ctx.period_end or date(y, 12, 31)
    alltext = [(d, d.text) for d in docs]
    near: list[tuple[dict, Hit]] = []
    for d, text in alltext:
        for m in find_maturities(text, as_of):
            if m["months_from_balance_sheet"] <= 24 and not any(n[0]["maturity"] == m["maturity"] for n in near):
                hit = find([d], r"matur\w*(?: date\w*)?(?: of| on| is)?\s+" + re.escape(parse_date_str(m["maturity"])))
                if hit:
                    near.append((m, hit))
    if near:
        fcf = ctx.fact("free_cash_flow", y)
        neg = bool(fcf and fcf["value"] < 0)
        first = min(near, key=lambda n: n[0]["months_from_balance_sheet"])[0]
        ev = [ev_excerpt(h) for _, h in near] + ([ev_fact(fcf)] if fcf else []) + [
            {"kind": "calculation", "metric": "months_to_maturity", "formula": "months between balance-sheet date and maturity",
             "value": [n[0]["months_from_balance_sheet"] for n in near], "unit": "months",
             "inputs": [{"balance_sheet_date": as_of.isoformat(), "maturities": [n[0]["maturity"] for n in near]}]},
            ev_assumption("maturity_window_months", 24, "analyst convention"),
            ev_count("maturities_in_window", len(near), "distinct maturity dates within the window")]
        out.append(finding("FIN.MATURITY_WALL", agent, "financial", "critical" if neg else "high", "calculation",
                           "Debt maturity wall within 24 months",
                           f"{len(near)} debt maturity date(s) fall within 24 months of the {as_of.isoformat()} balance "
                           f"sheet; the first is {first['months_from_balance_sheet']} months out ({first['maturity']})."
                           + (" Free cash flow was negative, so repayment depends on refinancing." if neg else ""), ev))
    # going-concern doubt (ASC 205-40): only an AFFIRMATIVE statement counts. Hypothetical risk-factor wording
    # ("could raise substantial doubt") and the standard's own description ("evaluate whether there are conditions
    # ... that raise substantial doubt") do not. Added in release 1.2 after the blind benchmark exposed the gap.
    gc = find(docs, GOING_CONCERN)
    if gc and not re.search(r"alleviat", gc.match.group(0), re.I):
        out.append(finding("FIN.GOING_CONCERN", agent, "financial", "critical", "source_fact",
                           "Substantial doubt about ability to continue as a going concern",
                           "The filing states that conditions raise substantial doubt about the company's ability to "
                           "continue as a going concern.", [ev_excerpt(gc)]))
    for code, pattern, title, sev, detail in [
        ("FIN.CANNOT_REPAY_IF_ACCELERATED", r"will not have sufficient cash to repay",
         "Company states it could not repay debt if accelerated", "high",
         "The filing states that if lenders demanded payment the company would not have sufficient cash to repay."),
        ("FIN.PIK_INTEREST", r"paid-in-kind|paid in kind", "Paid-in-kind interest on debt", "medium",
         "Part of the interest on the company's debt is paid in kind (added to principal)."),
        ("FIN.COVENANT_WAIVER_HISTORY", r"waiver with respect to the [^.]{0,60}covenant", "History of covenant waivers", "high",
         "Lenders previously waived a financial covenant for the company."),
    ]:
        hit = find(docs, pattern)
        if hit:
            out.append(finding(code, agent, "financial", sev, "source_fact", title, detail, [ev_excerpt(hit)]))
    # minimum EBITDA covenant (definition mismatch -> interpretation)
    mh = find(docs, r"minimum [^.]{0,80}?EBITDA of \$(\d+(?:\.\d+)?) million")
    e = ctx.fact("ebitda", y)
    if mh and e:
        thr = float(mh.match.group(1))
        head = (e["value"] - thr) / e["value"] * 100 if e["value"] > 0 else None
        out.append(finding("FIN.MIN_EBITDA_COVENANT", agent, "financial", "medium" if head is None or head < 50 else "low",
                           "interpretation", "Minimum EBITDA covenant (approximate headroom)",
                           f"Credit agreements require minimum adjusted EBITDA of ${thr:.1f} million. FY{y} EBITDA "
                           f"calculated as operating income + D&A was {fmt(e['value'], 'USD_millions')}"
                           + (f", about {fmt(head, 'pct')} above the minimum." if head is not None else "."),
                           [ev_excerpt(mh), ev_fact(e)] + ([ev_count("approx_headroom_pct", head,
                                                                     "(ebitda - minimum) / ebitda * 100")] if head is not None else []),
                           "The covenant uses the lenders' adjusted EBITDA definition; this comparison uses unadjusted "
                           "EBITDA and is an approximation."))
    # floating-rate debt in a rising-rate year (FRED)
    fl = find(ctx.by_types(["financial_notes", "management"]),
              r"(?:variable|floating) interest rate|Eurodollar rate|SOFR\s*\+|LIBOR")
    pts = [p for p in ctx.macro.get("FEDFUNDS", []) if p["date"].startswith(str(y)) and p["value"] is not None]
    lev = ctx.fact("net_leverage_x", y)
    if fl and len(pts) >= 2 and lev and lev["value"] > 1.0:  # rate exposure only matters with material net debt
        a, b = pts[0], pts[-1]
        if b["value"] - a["value"] >= 1.0:
            out.append(finding("FIN.FLOATING_RATE_RISING", agent, "financial", "medium", "source_fact",
                               "Floating-rate debt during rising policy rates",
                               f"Debt terms reference floating benchmarks while the effective federal funds rate rose from "
                               f"{a['value']:.2f}% ({a['date'][:7]}) to {b['value']:.2f}% ({b['date'][:7]}) (FRED FEDFUNDS).",
                               [ev_excerpt(fl), ev_macro("FEDFUNDS", [a, b]), ev_fact(lev)],
                               "Hedging, if any, is not assessed."))
    return out


GOING_CONCERN = (r"(?:\b(?:These|Those|Such|The foregoing|The above)\b"
                 r"(?:(?!\b(?:could|may|might|would|will|not|no|if|whether)\b)[^.]){0,80}?\braises?"
                 r"|\bthere is)\s+substantial doubt "
                 r"(?:about|as to|regarding) (?:the Company['’]s|our|its|the Corporation['’]s) ability to continue as a "
                 r"going concern")


def parse_date_str(iso: str) -> str:
    d = date.fromisoformat(iso)
    return d.strftime("%B ") + str(d.day) + d.strftime(", %Y")


# ----------------------------------------------------------------------------- legal counsel
CLAUSE_LABELS = {"change_of_control": "Change-of-control triggers", "termination_for_convenience":
                 "Termination rights exercisable by counterparties", "most_favoured_nation": "Most-favoured-nation pricing obligation",
                 "assignment_restriction": "Contracts require consent to assign", "mandatory_prepayment":
                 "Debt must be repaid on change of control", "unlimited_liability": "Uncapped liability for third-party losses",
                 "reserve_requirement": "Sponsor bank can impose cash reserves", "financial_covenant": "Maintenance financial covenants",
                 "exclusivity": "Exclusivity restrictions", "auto_renewal": "Auto-renewal terms"}


@safe_node("legal_counsel")
def legal_counsel(state: DDState) -> dict:
    t0, agent = time.perf_counter(), "legal_counsel"
    ctx = _ctx(state)
    docs = ctx.by_types(["legal"])                       # contracts, legal memos, 10-K Item 3
    notes = ctx.by_types(["legal", "financial_notes"])   # + 10-K notes (commitments, contingencies, debt)
    out: list[dict] = []
    by_clause: dict[str, list[Hit]] = {}
    for d in docs:
        for h in scan_clauses(d.text, use_model=False):
            if h["source"] != "rule":
                continue  # ML suggestions are surfaced only as part of LLM review, never as facts
            hit = find([d], re.escape(h["match"]))
            if hit:
                by_clause.setdefault(h["clause"], []).append(hit)
    for clause, hits in by_clause.items():
        sev = CLAUSE_RULES[clause][1]
        out.append(finding(f"LEG.CLAUSE.{clause}", agent, "legal", sev, "source_fact", CLAUSE_LABELS.get(clause, clause),
                           f"{len(hits)} provision(s) found in {', '.join(sorted({h.doc.filename for h in hits}))}.",
                           [ev_excerpt(h) for h in hits[:3]] + [ev_count("provisions", len(hits), "rule matches")]))
    lit = find(notes, r"(?:damages|plaintiffs? seek)[^.]{0,80}?\$(\d+(?:\.\d+)?) million")
    if lit:
        no_reserve = bool(re.search(r"No reserve has been recorded", lit.doc.text))
        out.append(finding("LEG.LITIGATION", agent, "legal", "high", "source_fact", "Material pending litigation",
                           f"Pending claim with damages estimated at ${lit.match.group(1)} million"
                           + ("; no reserve has been recorded." if no_reserve else "."), [ev_excerpt(lit)]
                           + ([ev_excerpt(find([lit.doc], r"No reserve has been recorded"))] if no_reserve else [])))
    env = find(notes, r"remediation cost estimated at \$(\d+(?:\.\d+)?) million")
    if env:
        out.append(finding("LEG.ENVIRONMENTAL", agent, "legal", "medium", "source_fact", "Environmental remediation liability",
                           f"Remediation cost estimated at ${env.match.group(1)} million.", [ev_excerpt(env)]))
    br = find(docs, r"unauthori[sz]ed party accessed")
    if br:
        out.append(finding("LEG.DATA_INCIDENT", agent, "legal", "medium", "source_fact", "Prior data security incident",
                           "An unauthorised party accessed company systems; regulatory notifications were filed.", [ev_excerpt(br)]))
    for h in find_all(notes, r"accounted for (\d+)% of [^.]{0,40}revenue"):
        pct = int(h.match.group(1))
        if pct >= 20:
            tfc = re.search(r"termination for convenience", h.doc.text, re.I)
            ev = [ev_excerpt(h)] + ([ev_excerpt(find([h.doc], r"termination for convenience"))] if tfc else [])
            out.append(finding("LEG.CUSTOMER_CONCENTRATION", agent, "legal", "critical" if tfc else "high", "source_fact",
                               "Severe customer concentration",
                               f"A single customer accounted for {pct}% of revenue"
                               + (" and its contract allows termination for convenience." if tfc else "."), ev))
            break
    terms = find(docs, r"extended from (\d+) days to (\d+) days")
    if terms:
        out.append(finding("LEG.PAYMENT_TERMS", agent, "legal", "medium", "source_fact", "Customer payment terms extended",
                           f"Payment terms were extended from {terms.match.group(1)} to {terms.match.group(2)} days.",
                           [ev_excerpt(terms)]))
    extra, llm = _llm_extra(agent, ["legal"], ctx, state, out, ["legal", "financial_notes"])
    out += extra
    cov = _coverage(agent, ["legal", "financial_notes"], notes, rules=len(CLAUSE_RULES) + 5, categories=_categories(agent, ctx, out),
                    matches=sum(map(len, by_clause.values())) + sum(1 for f in out if not f["code"].startswith("LEG.CLAUSE")),
                    findings=len(out), llm=llm)
    return {"findings": out, "coverage": [cov], "events": [_event(agent, f"Scanned {len(notes)} document(s) ({len(docs)} legal, "
                                                     f"{len(notes) - len(docs)} financial notes); "
                                                     f"{sum(map(len, by_clause.values()))} clause matches in {len(by_clause)} "
                                                     f"families; {len(out)} candidate findings.", t0)]}


# ----------------------------------------------------------------------------- market strategist
@safe_node("market_strategist")
def market_strategist(state: DDState) -> dict:
    t0, agent = time.perf_counter(), "market_strategist"
    ctx = _ctx(state)
    docs = ctx.by_types(["market"])
    y = ctx.latest_year
    out: list[dict] = []
    cagr = find(docs, r"(\d+(?:\.\d+)?)% CAGR")
    g = ctx.fact("revenue_growth_pct", y)
    if cagr and g and g["value"] > 2 * float(cagr.match.group(1)):
        out.append(finding("MKT.GROWTH_VS_MARKET", agent, "market", "medium", "interpretation",
                           "Growth far above market — sustainability unproven",
                           f"Revenue grew {fmt(g['value'], 'pct')} in FY{y} versus a market forecast at "
                           f"{cagr.match.group(1)}% CAGR; the gap implies share gains that need validating.",
                           [ev_fact(g), ev_excerpt(cagr)]))
    mr = find(docs, r"EBITDA margins[^.]{0,80}?(\d+)% to (\d+)%")
    em = ctx.fact("ebitda_margin_pct", y)
    if mr and em:
        lo, hi = float(mr.match.group(1)), float(mr.match.group(2))
        pos = "within" if lo <= em["value"] <= hi else ("above" if em["value"] > hi else "below")
        out.append(finding("MKT.MARGIN_VS_PEERS", agent, "market", "low", "calculation", f"EBITDA margin {pos} peer range",
                           f"FY{y} EBITDA margin of {fmt(em['value'], 'pct')} is {pos} the {lo:g}%–{hi:g}% peer range.",
                           [ev_fact(em), ev_excerpt(mr)]))
    for code, pattern, title, sev in [
        ("MKT.PRICING_PRESSURE", r"pricing pressure of (\d+)-(\d+)%", "Structural pricing pressure", "medium"),
        ("MKT.TAKE_RATE", r"take rates are compressing by (\d+)-(\d+) basis points", "Take-rate compression", "medium"),
        ("MKT.HIGH_RISK_VERTICALS", r"high-risk verticals", "Portfolio concentrated in high-risk verticals", "high"),
        ("MKT.DISRUPTION", r"large carriers moving downmarket|digital freight brokers", "Competitive disruption threat", "medium"),
    ]:
        hit = find(docs, pattern)
        if hit:
            out.append(finding(code, agent, "market", sev, "source_fact", title, hit.excerpt.strip()[:300], [ev_excerpt(hit)]))
    extra, llm = _llm_extra(agent, ["market"], ctx, state, out, ["market", "business"])
    out += extra
    described = ctx.by_types(["business", "risk_factors"])   # the company's own description (reviewed for presence)
    cov = _coverage(agent, ["market", "business", "risk_factors"], docs + described,
                    facts_used=sum(1 for x in (g, em) if x), rules=6, categories=_categories(agent, ctx, out),
                    matches=len(out) - len(extra), findings=len(out), llm=llm)
    return {"findings": out, "coverage": [cov], "events": [_event(agent, f"Reviewed {len(docs)} independent market "
                                                     f"document(s) and {len(described)} company description(s); "
                                                     f"{len(out)} candidate findings.", t0)]}


# ----------------------------------------------------------------------------- ESG & compliance
ESG_RULES = [
    ("ESG.MATERIAL_WEAKNESS", r"(?:identified|noted|reported|disclosed)\s+a\s+material weakness", "esg", "high",
     "Material weakness in internal controls", lambda m: "A material weakness in internal control was reported."),
    ("ESG.BOARD_INDEPENDENCE", r"(\w+) members, (\w+) of whom are independent", "esg", "medium",
     "Board lacks independent majority",
     lambda m: f"Only {_WORDNUM.get(m.group(2).lower(), m.group(2))} of {_WORDNUM.get(m.group(1).lower(), m.group(1))} directors are independent."),
    ("ESG.TURNOVER", r"turnover was (\d+)% [^.]{0,40}\(industry average approx\. (\d+)%\)", "esg", "medium",
     "Elevated workforce turnover", lambda m: f"Turnover of {m.group(1)}% vs industry average of about {m.group(2)}%."),
    ("ESG.EMISSIONS", r"emissions of ([\d,]+) tCO2e, up (\d+)%", "esg", "medium", "Rising emissions",
     lambda m: f"Scope 1 emissions rose {m.group(2)}%."),
    ("ESG.UNIONISED", r"represented approximately (\d+)% of our workforce", "esg", "medium", "Highly unionised workforce",
     lambda m: f"About {m.group(1)}% of the workforce is represented by a union."),
    ("ESG.PENSION_CRITICAL", r"Critical\s+and\s+Declining", "esg", "high",
     "Multi-employer pension plans in critical and declining status",
     lambda m: "The company participates in multi-employer pension plans in 'critical and declining' status under the "
               "Pension Protection Act; withdrawal can trigger large liabilities."),
    ("CMP.CHARGEBACKS", r"chargeback ratio reached ([\d.]+)%[^.]{0,40}above the ([\d.]+)%", "compliance", "critical",
     "Chargebacks above card-network threshold",
     lambda m: f"Chargeback ratio of {m.group(1)}% exceeds the {m.group(2)}% network threshold."),
    ("CMP.PCI_LAPSED", r"Attestation of Compliance expired", "compliance", "critical", "PCI DSS attestation lapsed",
     lambda m: "The PCI DSS Attestation of Compliance has expired."),
    ("CMP.KYC_GAPS", r"(\d+) files \(([\d.]+)%\) lacked beneficial ownership", "compliance", "high", "KYC/AML file deficiencies",
     lambda m: f"{m.group(1)} sampled merchant files ({m.group(2)}%) lacked beneficial-ownership verification."),
    ("CMP.SANCTIONS", r"sanctions screening is performed at onboarding only", "compliance", "high",
     "No ongoing sanctions screening", lambda m: "Sanctions screening is performed only at onboarding."),
    ("CMP.LICENSING", r"licences in (\d+) states are pending", "compliance", "medium", "Incomplete licensing footprint",
     lambda m: f"Money transmitter licences are pending in {m.group(1)} states."),
    ("CMP.VULN_REMEDIATION", r"remediated after (\d+) days", "compliance", "medium", "Slow remediation of critical vulnerability",
     lambda m: f"A critical vulnerability took {m.group(1)} days to remediate."),
]


ESG_DOC_TYPES = ["esg", "compliance", "legal", "risk_factors", "financial_notes", "controls", "business"]


@safe_node("esg_compliance")
def esg_compliance(state: DDState) -> dict:
    t0, agent = time.perf_counter(), "esg_compliance"
    ctx = _ctx(state)
    docs = ctx.by_types(ESG_DOC_TYPES)
    out: list[dict] = []
    for code, pattern, cat, sev, title, detail in ESG_RULES:
        hit = find(docs, pattern)
        if hit:
            ev = [ev_excerpt(hit)]
            words = [g for g in hit.match.groups() if g and g.lower() in _WORDNUM]
            if words:  # numbers written as words in the source ("two of whom")
                ev.append(ev_count("numbers_in_words", [_WORDNUM[w.lower()] for w in words], f"words {words} as numbers"))
            out.append(finding(code, agent, cat, sev, "source_fact", title, detail(hit.match), ev))
    cba = find(docs, r"(?:collective bargaining|labor) agreements?[^.]{0,200}?(?:in effect|expir\w*) (?:through|on) "
                     r"((?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4})")
    if cba and ctx.period_end:
        exp = parse_date(cba.match.group(1))
        months = months_between(ctx.period_end, exp)
        if 0 <= months <= 24:
            out.append(finding("ESG.LABOUR_AGREEMENT_EXPIRY", agent, "esg", "high", "calculation",
                               "Labour agreement expires within 24 months",
                               f"The collective bargaining agreement runs through {exp.isoformat()}, {months} months after "
                               f"the {ctx.period_end.isoformat()} balance sheet.",
                               [ev_excerpt(cba), {"kind": "calculation", "metric": "months_to_expiry", "value": months,
                                                  "unit": "months", "formula": "months between balance-sheet date and expiry",
                                                  "inputs": [{"balance_sheet_date": ctx.period_end.isoformat(),
                                                              "expiry": exp.isoformat()}]},
                                ev_assumption("window_months", 24, "analyst convention")]))
    extra, llm = _llm_extra(agent, ["esg", "compliance"], ctx, state, out, ["esg", "compliance", "risk_factors"])
    out += extra
    cov = _coverage(agent, ESG_DOC_TYPES, docs, rules=len(ESG_RULES) + 1, matches=len(out) - len(extra),
                    categories=_categories(agent, ctx, out),
                    findings=len(out), llm=llm)
    return {"findings": out, "coverage": [cov], "events": [_event(agent, f"Reviewed {len(docs)} ESG/compliance-relevant document(s); "
                                                     f"{len(out)} candidate findings.", t0)]}


# ----------------------------------------------------------------------------- red team
@safe_node("red_team")
def red_team(state: DDState) -> dict:
    """Cross-examines management statements against independent evidence. Contradictions are labelled
    'interpretation' and must carry both sides of the evidence."""
    t0, agent = time.perf_counter(), "red_team"
    ctx = _ctx(state)
    mgmt = ctx.by_types(["management"])
    y = ctx.latest_year
    prior = state.get("findings", [])
    by_code = {f["code"]: f for f in prior}

    def first(prefix: str) -> dict | None:
        return next((f for c, f in by_code.items() if c.startswith(prefix)), None)

    out: list[dict] = []

    def contradict(code: str, hit: Hit, other_ev: list[dict], title: str, detail: str):
        out.append(finding(code, agent, "consistency", "critical", "interpretation", title, detail,
                           [ev_excerpt(hit)] + other_ev))

    g = ctx.fact("revenue_growth_pct", y)
    if (h := find(mgmt, r"revenue grew (\d+(?:\.\d+)?)%")) and g and abs(float(h.match.group(1)) - g["value"]) > 3:
        contradict("RED.GROWTH_OVERSTATED", h, [ev_fact(g)], "Management overstates revenue growth",
                   f"Management states {h.match.group(1)}% revenue growth; the financial statements give "
                   f"{fmt(g['value'], 'pct')} for FY{y}.")
    em = ctx.fact("ebitda_margin_pct", y)
    if (h := find(mgmt, r"EBITDA margin of (\d+(?:\.\d+)?)%")) and em and abs(float(h.match.group(1)) - em["value"]) > 2:
        contradict("RED.MARGIN_OVERSTATED", h, [ev_fact(em)], "Management overstates EBITDA margin",
                   f"Management states an EBITDA margin of {h.match.group(1)}%; calculated FY{y} margin is "
                   f"{fmt(em['value'], 'pct')}.")
    for code, pat, src_prefix, title, text in [
        ("RED.UNDISCLOSED_LITIGATION", r"not party to any material litigation", "LEG.LITIGATION",
         "Undisclosed material litigation", "Management states there is no material litigation; counsel's memo describes a pending claim."),
        ("RED.CONCENTRATION_DENIED", r"no single customer represents a material share", "LEG.CUSTOMER_CONCENTRATION",
         "Customer diversification claim is false", "Management describes a diversified customer base; the customer contracts show a single customer with a material revenue share."),
        ("RED.LEVERAGE_NARRATIVE", r"conservative leverage|ample covenant headroom", "FIN.COVENANT_BREACH",
         "Leverage narrative contradicts covenant position", "Management describes conservative leverage; calculated leverage breaches the covenant."),
        ("RED.PCI_CLAIM", r"fully PCI DSS compliant", "CMP.PCI_LAPSED", "PCI compliance claim is not supported",
         "Management claims full PCI DSS compliance; the compliance assessment says the attestation expired."),
        ("RED.LICENSING_CLAIM", r"licensed in all 50 states", "CMP.LICENSING", "Licensing claim overstated",
         "Management claims licences in all 50 states; the compliance assessment lists pending licences."),
        ("RED.CHARGEBACK_CLAIM", r"chargeback rates well below", "CMP.CHARGEBACKS",
         "Risk-management claim contradicted by chargeback data", "Management claims low chargebacks; the compliance assessment shows a ratio above the network threshold."),
        ("RED.FUNDING_CLAIM", r"funded from operating cash flow", "FIN.NEGATIVE_FCF",
         "Expansion plan not fundable from operating cash flow", "Management plans to fund expansion from operating cash flow; free cash flow is negative."),
    ]:
        h = find(mgmt, pat)
        src = first(src_prefix)
        if h and src:
            contradict(code, h, src["evidence"][:2], title, text)
    wall = by_code.get("FIN.MATURITY_WALL")
    if wall and mgmt and not any(re.search(r"refinanc", d.text, re.I) for d in mgmt):
        h = find(mgmt, r"Management expects|we expect|management believes|Liquidity") or find(mgmt, r"\w{4,}")
        out.append(finding("RED.NO_REFINANCING_PLAN", agent, "consistency", "high", "interpretation",
                           "Management discussion does not address refinancing",
                           "Debt maturities fall within 24 months of the balance sheet, but the management discussion "
                           "documents contain no discussion of refinancing.",
                           [ev_excerpt(h)] + [e for e in wall["evidence"] if e["kind"] == "document_excerpt"][:1]
                           + [ev_assumption("maturity_window_months", 24, "analyst convention")],
                           "Absence of a word in the MD&A is an indicator, not proof that no plan exists."))
    # Coverage gaps: a workstream that examined no documents (or no facts) is a diligence gap, not a clean result.
    for c in state.get("coverage", []):
        if c.get("status") == "failed":
            continue   # failures already make the run incomplete
        req = next((k for k in c.get("categories", []) if k["required"] and k["status"] == "insufficient_evidence"
                    and k["doc_types"]), None)
        if c["agent"] == "financial_analyst" and c["facts_used"] == 0:
            gap, types = "no reported financial facts", c["doc_types"]
        elif req:
            gap, types = f"{req['label'].lower()}: no documents of type {', '.join(req['doc_types'])}", req["doc_types"]
        elif c["doc_types"] and c["documents_reviewed"] == 0 and c["agent"] != "financial_analyst":
            gap, types = f"no documents of type {', '.join(c['doc_types'])}", c["doc_types"]
        else:
            continue
        name = c["agent"].replace("_", " ")
        out.append(finding(f"RED.COVERAGE_GAP.{c['agent']}", agent, "operational", "medium", "source_fact",
                           f"Diligence gap in the {name} workstream" + (f": {req['label'].lower()}" if req else ""),
                           f"The {name} workstream had 0 documents for a required evidence category ({gap}). Those "
                           "risks are unassessed, not cleared; obtain the missing material before relying on this analysis.",
                           [{"kind": "calculation", "metric": "documents_reviewed", "value": 0, "unit": "count",
                             "formula": "documents in the data room of the searched types", "inputs": [{"doc_types": types}]}],
                           "Coverage is measured by document type; a document filed under another type is not counted."))
    if not mgmt:
        out.append(finding("RED.COVERAGE_GAP.red_team", agent, "operational", "low", "source_fact",
                           "Red team could not cross-examine management statements",
                           "No management discussion documents in the data room, so 0 management claims could be "
                           "tested against the evidence.",
                           [{"kind": "calculation", "metric": "documents_reviewed", "value": 0, "unit": "count",
                             "formula": "documents in the data room of the searched types",
                             "inputs": [{"doc_types": ["management"]}]}]))
    inj = find(ctx.docs, r"NEUTRALISED_INSTRUCTION")
    if inj:
        out.append(finding("RED.EMBEDDED_INSTRUCTIONS", agent, "consistency", "high", "source_fact",
                           "Embedded instructions detected in data-room document",
                           f"{inj.doc.filename} contains text that tries to instruct the AI reviewers; it was neutralised "
                           "at ingestion. Treat the document's provenance as suspect.", [ev_excerpt(inj)]))
    cov = _coverage(agent, ["management"], mgmt, facts_used=sum(1 for x in (g, em) if x), rules=12,
                    matches=len(out), findings=len(out), llm="not_used")
    return {"findings": out, "coverage": [cov],
            "events": [_event(agent, f"Cross-examined {len(mgmt)} management document(s) and "
                                     f"{len(state.get('coverage', []))} workstream coverage record(s); {len(out)} "
                                     "contradiction(s) or gaps found.", t0)]}


# ----------------------------------------------------------------------------- quality gate
def quality_gate(state: DDState) -> dict:
    t0 = time.perf_counter()
    ctx = load_context(state["deal"]["id"])
    res = run_quality_gate(state.get("findings", []), ctx, state.get("agent_errors", []))
    msg = (f"Verified {sum(f['verification_status'] == 'verified' for f in res['validated'])} and supported "
           f"{sum(f['verification_status'] == 'supported' for f in res['validated'])} of {len(state.get('findings', []))} "
           f"candidate findings; rejected {len(res['rejected'])}. ")
    if res["incomplete"]:
        msg += f"Run INCOMPLETE: {len(state.get('agent_errors', []))} agent(s) failed — not eligible for approval."
    else:
        msg += f"Risk score {res['risk_score']}/100 → {res['recommendation']}."
    return {"validated_findings": res["validated"], "rejected_findings": res["rejected"],
            "risk_score": res["risk_score"], "risk_breakdown": res["breakdown"],
            "recommendation": res["recommendation"], "incomplete": res["incomplete"],
            "events": [_event("quality_gate", msg, t0, "error" if res["incomplete"] else "ok")]}


def route_after_gate(state: DDState) -> str:
    return "__end__" if state.get("incomplete") else "human_review"


def human_review(state: DDState) -> dict:
    decision = interrupt({"risk_score": state["risk_score"], "recommendation": state["recommendation"],
                          "n_findings": len(state["validated_findings"])})
    return {"review": decision, "events": [{"agent": "human_review", "latency_ms": 0, "status": "ok",
            "message": f"Partner decision: {decision.get('decision')} by {decision.get('reviewer')}."}]}
