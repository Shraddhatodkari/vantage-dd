"""Investment committee memo, rendered only from the persisted, approved analysis version."""
from __future__ import annotations

from app.agents.quality import SCALE_K, SEVERITY_WEIGHT, STATUS_FACTOR, THRESHOLDS
from app.analytics.metrics import fmt

ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
CLAIM_ORDER = {"calculation": 0, "source_fact": 1, "interpretation": 2, "assumption": 3}
CAT_ORDER = {"financial": 0, "legal": 1, "compliance": 2, "consistency": 3, "esg": 4, "market": 5, "operational": 6}
DEAL_TYPES = {"m_and_a": "M&A", "credit": "Credit review", "vendor_risk": "Third-party / vendor risk"}
CONDITIONS = [  # (finding code prefix, condition precedent)
    ("FIN.COVENANT_BREACH", "Obtain a lender waiver or amendment before signing."),
    ("FIN.MATURITY_WALL", "Obtain committed refinancing (or a credible refinancing plan) for maturities inside 24 months."),
    ("FIN.NEGATIVE_EBITDA", "Underwrite on a restructuring / recovery basis: earnings do not cover the existing debt."),
    ("FIN.GOING_CONCERN", "Do not lend on the standing balance sheet: require a committed restructuring or refinancing plan and lender support before committing."),
    ("FIN.CANNOT_REPAY", "Stress-test liquidity under an acceleration scenario; require lender standstill comfort."),
    ("LEG.LITIGATION", "Specific indemnity and escrow sized to the litigation exposure."),
    ("LEG.CUSTOMER_CONCENTRATION", "Key-customer consent to assignment and a multi-year extension."),
    ("RED.GROWTH_OVERSTATED", "Re-base the valuation on reported figures, not management's presentation."),
    ("RED.MARGIN_OVERSTATED", "Re-base the valuation on reported figures, not management's presentation."),
    ("CMP.", "Remediation plan signed off by the sponsor bank / network as a closing condition."),
    ("ESG.MATERIAL_WEAKNESS", "Quality-of-earnings review focused on the reported control weakness."),
    ("ESG.PENSION_CRITICAL", "Quantify potential multi-employer pension withdrawal liability before committing."),
    ("ESG.LABOUR_AGREEMENT_EXPIRY", "Assess labour-negotiation scenarios against the refinancing timetable."),
]
DISCLAIMER = ("The recommendation is a risk-screening output of this methodology over the evidence listed, not a "
              "guarantee, credit rating or investment advice. 'Proceed' means no verified finding crossed the "
              "thresholds — it does not mean risks outside the reviewed material are absent.")
SOURCE_NAME = {"sec_filing": "SEC EDGAR Form 10-K", "sec_companyfacts": "SEC XBRL company facts",
               "sec_submissions": "SEC EDGAR submissions index", "gleif": "GLEIF LEI records", "fred": "FRED (St. Louis Fed)"}
MODE_LABEL = {"live": "retrieved live from the source at the time shown",
              "snapshot": "stored snapshot (retrieved at the time shown; not re-checked since)"}
CLAIM_LABEL = {"source_fact": "source fact", "calculation": "calculation", "interpretation": "interpretation",
               "assumption": "assumption"}
KEY_METRICS = [("revenue", "Revenue"), ("revenue_growth_pct", "Revenue growth"), ("ebitda", "EBITDA"),
               ("ebitda_margin_pct", "EBITDA margin"), ("net_income", "Net income"), ("total_debt", "Total debt"),
               ("cash", "Cash"), ("gross_leverage_x", "Gross leverage (total debt / EBITDA)"),
               ("net_leverage_x", "Net leverage (net debt / EBITDA)"), ("interest_coverage_x", "EBITDA / interest"),
               ("interest_expense", "Interest expense"), ("current_ratio_x", "Current ratio"),
               ("operating_cash_flow", "Operating cash flow"), ("capex", "Capital expenditure"),
               ("free_cash_flow", "Free cash flow")]


def _ev_line(e: dict) -> str:
    k = e["kind"]
    if k == "document_excerpt":
        src = f"[{e['filename']}]({e['source_url']})" if e.get("source_url") else e["filename"]
        acc = f", accession {e['accession']}" if e.get("accession") else ""
        loc = e.get("locator") or {}
        q = e["excerpt"].replace("\n", " ").strip()
        return f"> {src}{acc}, chars {loc.get('start')}–{loc.get('end')}: \"{q[:300]}{'…' if len(q) > 300 else ''}\""
    if k == "reported_fact":
        where = (f"{e.get('xbrl_tag')} in {e.get('form')} {e.get('accession')} filed {e.get('filed')}"
                 if e.get("xbrl_tag") else f"{e.get('source_document')}")
        return f"> Reported: {e['metric']} FY{e['fiscal_year']} = {e['display']} ({where})"
    if k == "calculation":
        if e.get("fact_id"):
            ins = "; ".join(f"{i['metric']} FY{i['fiscal_year']} = {fmt(i['value'], i.get('unit', ''))}" for i in e["inputs"])
            return f"> Calculated: {e['metric']} FY{e['fiscal_year']} = {e['display']} = {e['formula']} [{ins}]"
        return f"> Calculated: {e.get('metric')} = {e.get('value')} ({e.get('formula')})"
    if k == "assumption":
        return f"> Assumption: {e['name']} = {e['value']} ({e['basis']})"
    if k == "macro_series":
        obs = ", ".join(f"{o['date']}: {o['value']}" for o in e["observations"])
        return f"> FRED {e['series_id']} ({e.get('source_url')}, retrieved {e.get('retrieved_at')}): {obs}"
    return f"> {k}"


DEBT_CODES = ("FIN.MATURITY", "FIN.COVENANT", "FIN.MIN_EBITDA", "FIN.CANNOT_REPAY", "FIN.PIK", "FIN.FLOATING")
STATUS_TEXT = {"risk_found": "finding(s) raised", "reviewed_no_risk": "reviewed — no rule triggered",
               "insufficient_evidence": "insufficient evidence", "not_performed": "not performed"}


def _findings_block(L: list[str], group: list[dict], pts: dict) -> None:
    for f in group:
        p = pts.get((f["code"], f["title"]), {}).get("points")
        L.append(f"#### [{f['severity'].upper()}] {f['title']}  `{f['code']}`")
        L.append(f"*{f['agent']} · {f['category']} · {CLAIM_LABEL.get(f['claim_type'], f['claim_type'])} · "
                 f"{f['verification_status']}{f' · {p} score points' if p is not None else ''}*  ")
        L.append(f["detail"])
        if f.get("limitations"):
            L.append(f"*Limitation:* {f['limitations']}")
        L += [_ev_line(e) for e in f["evidence"][:4]]
        L.append("")


def build_report(d: dict) -> str:
    from app.agents.quality import contributions
    deal, run, comp = d["deal"], d["run"], d.get("company") or {}
    vf = sorted(d["validated"], key=lambda f: (ORDER[f["severity"]], CLAIM_ORDER.get(f["claim_type"], 9),
                                               CAT_ORDER.get(f["category"], 9), f["code"]))
    rej = d["rejected"]
    pts = contributions(vf, run["risk_score"])
    cls = deal["data_classification"]
    banner = {"verified_real": "VERIFIED REAL DATA — every input comes from the retrieved sources listed below"
                               + (" · HISTORICAL CASE" if deal.get("is_historical") else ""),
              "illustrative": "ILLUSTRATIVE — SYNTHETIC DEMO DATA, NOT A REAL COMPANY",
              "user_supplied": "USER-SUPPLIED DOCUMENTS — not independently verified"}[cls]
    L = [f"# Investment Committee Memo — {deal['name']}", "", f"**{banner}**", "",
         "| | |", "|---|---|",
         f"| Target | {deal['target_company']} |",
         f"| Analysis type | {DEAL_TYPES.get(deal['deal_type'], deal['deal_type'])} · {deal['sector']} |"]
    if comp:
        lei = (f"{comp['lei']} ({comp.get('lei_status')})" if comp.get("lei")
               else f"not verified ({(comp.get('lei_match') or 'not looked up').replace('_', ' ')}) — manual check required")
        L += [f"| SEC CIK | {comp.get('cik')} (current tickers: {', '.join(comp.get('tickers') or []) or 'none'}) |",
              f"| GLEIF LEI (current identity metadata, not as of the cut-off; not used in scoring) | {lei} |"]
    L += [f"| Reporting period end | {deal.get('reporting_period_end') or 'n/a'} |"]
    if d.get("historical_cutoff"):
        L.append(f"| Historical cut-off | information filed or published on or before {d['historical_cutoff']} |")
    L += [f"| Analysis run | version {run['version']} (run {run['id'][:8]}), started {run['created_at']} |",
          f"| Inputs fingerprint | `{(run.get('inputs_hash') or '')[:16]}` |",
          f"| Methodology | {run['methodology_version']} |",
          f"| Source data | {d.get('source_mode_text') or 'see Sources'} |",
          f"| Currency / units | {deal.get('currency', 'USD')}; money in millions unless stated |", ""]

    # 1. executive summary
    sev = {k: sum(1 for f in vf if f["severity"] == k) for k in ORDER}
    cov = d.get("coverage") or []
    gaps = [(c["agent"], k) for c in cov for k in c.get("categories", []) if k["status"] == "insufficient_evidence"]
    L += ["## 1. Executive summary", "",
          f"**Recommendation: {run['recommendation']}** — risk score {run['risk_score']}/100 (methodology "
          f"{run['methodology_version']}).", "", f"*{DISCLAIMER}*", "",
          f"Accepted findings: {sev['critical']} critical, {sev['high']} high, {sev['medium']} medium, {sev['low']} low; "
          f"{len(rej)} rejected by the quality gate. Evidence categories with insufficient evidence: {len(gaps)}.", ""]
    top = [f for f in vf if f["severity"] in ("critical", "high")]
    if top:
        L += ["The findings that drive the recommendation:", ""]
        L += [f"{i}. **{f['title']}** — {f['detail']}" for i, f in enumerate(top[:3], 1)] + [""]
    else:
        L += ["No high or critical findings passed verification."]
        med = [f for f in vf if f["severity"] == "medium"]
        if med:
            L += ["Medium findings: " + "; ".join(f["title"] for f in med) + "."]
        L.append("")

    # 2. credit thesis
    L += ["## 2. Credit thesis — positive evidence", ""]
    st = d.get("strengths") or []
    L += [f"- {x['text']}" for x in st] if st else ["- No strength met the methodology thresholds on the reported facts."]
    L += ["", "*Strengths are computed from the same reported facts and thresholds as the risk rules; they do not change "
          "the score.*", ""]

    # 3. material risks
    L += ["## 3. Material risks", ""]
    mat = [f for f in vf if f["severity"] in ("critical", "high", "medium")]
    if mat:
        L += ["| Severity | Finding | Type | Verification | Score points |", "|---|---|---|---|---|"]
        L += [f"| {f['severity']} | {f['title']} | {CLAIM_LABEL.get(f['claim_type'], f['claim_type'])} | "
              f"{f['verification_status']} | {pts.get((f['code'], f['title']), {}).get('points', '—')} |" for f in mat]
    else:
        L.append("No medium, high or critical findings passed verification.")
    L.append("")

    # 4. financial trends
    fin = d.get("financials") or []
    if fin:
        years = sorted({r["fiscal_year"] for r in fin})[-4:]
        L += ["## 4. Financial trends and ratios", "", "| Metric | " + " | ".join(f"FY{y}" for y in years) + " | Basis |",
              "|---|" + "---|" * len(years) + "---|"]
        idx = {(r["metric"], r["fiscal_year"]): r for r in fin}
        for m, label in KEY_METRICS:
            row = [idx.get((m, y)) for y in years]
            if not any(row):
                continue
            cells = [fmt(r["value"], r["unit"]) if r and r["value"] is not None else
                     (f"n/a ({r['status']})" if r else "n/a") for r in row]
            basis = next((("reported: " + (r["xbrl_tag"] or r.get("source_document") or "")) if r["kind"] == "reported"
                          else "calculated: " + (r["formula"] or "")) for r in row if r)
            L.append(f"| {label} | " + " | ".join(cells) + f" | {basis} |")
        L += ["", "EBITDA is operating income + depreciation & amortisation (unadjusted); it is not the lenders' adjusted "
              "EBITDA. Each figure is rounded on its own, so rounded inputs may not add up exactly.", ""]

    # 5. debt and covenants
    L += ["## 5. Debt maturities and covenant observations", ""]
    debt = [f for f in vf if f["code"].startswith(DEBT_CODES)]
    if debt:
        L += [f"- **{f['title']}** ({f['severity']}) — {f['detail']}" for f in debt]
    else:
        L.append("- No maturity or covenant rule was triggered on the reviewed documents.")
    for _, k in gaps:
        if k["key"] in ("debt_agreements", "covenants"):
            L.append(f"- {k['label']}: insufficient evidence ({k['basis']}); covenant definitions cannot be checked.")
    L.append("")

    # 6. detailed findings
    L += ["## 6. Detailed findings with evidence", ""]
    for ctype, heading in [("source_fact", "Stated in the sources"), ("calculation", "From calculations"),
                           ("interpretation", "Analytical interpretations (judgement on verified evidence)"),
                           ("assumption", "Resting on assumptions")]:
        group = [f for f in vf if f["claim_type"] == ctype]
        if group:
            L += [f"### {heading}", ""]
            _findings_block(L, group, pts)

    # 7. coverage and unresolved questions
    if cov:
        L += ["## 7. Evidence coverage and unresolved questions", "",
              "| Workstream | Documents reviewed | Reported facts | Calculated values | Rules evaluated | Rule matches | Findings | LLM | Limitation |",
              "|---|---|---|---|---|---|---|---|---|"]
        L += [f"| {c['agent'].replace('_', ' ')} | {c['documents_reviewed']} | {c['facts_used']} | {c.get('calculated_values', 0)} | {c['rules_evaluated']} | "
              f"{c['rule_matches']} | {c['candidate_findings']} | {c['llm'].replace('_', ' ')} | {c.get('limitation') or '—'} |"
              for c in cov] + [""]
        cats = [(c["agent"], k) for c in cov for k in c.get("categories", [])]
        if cats:
            L += ["| Workstream | Evidence category | Status | Basis |", "|---|---|---|---|"]
            L += [f"| {a.replace('_', ' ')} | {k['label']}{' (required)' if k['required'] else ''} | "
                  f"{STATUS_TEXT.get(k['status'], k['status'])} | {k['basis']} |" for a, k in cats] + [""]
    if d.get("historical_cutoff"):
        L += [f"**Historical cut-off:** only information filed or published on or before {d['historical_cutoff']} "
              "was used; the quality gate removes any later evidence.", ""]
    L += ["### Missing evidence and limitations", ""]
    gapsf = [r for r in fin if r["status"] != "ok"]
    if gapsf:
        L += [f"- {r['metric']} FY{r['fiscal_year']}: {r['status']} — {r.get('status_reason') or ''}" for r in gapsf[:15]]
    recon = [r for r in fin if r.get("document_check") not in (None, "matched", "not_checked") and r["kind"] == "reported"]
    if recon:
        L += [f"- {r['metric']} FY{r['fiscal_year']}: reconciliation to filing text = {r['document_check']}" for r in recon]
    revs = [r for r in fin if r.get("revision_note")]
    L += [f"- {r['metric']} FY{r['fiscal_year']}: {r['revision_note']}" for r in revs]
    if rej:
        L += [f"- Claim rejected by the quality gate: \"{f['title']}\" — {'; '.join(f['verification_notes'])[:200]}" for f in rej]
    L += ["- Findings come from deterministic rules over the documents provided; absence of a finding is not "
          "evidence that a risk is absent.",
          "- Thresholds marked 'analyst convention' are assumptions of this methodology, not contractual terms.", ""]

    # 8. follow-up
    conds = []
    for prefix, text in CONDITIONS:
        if any(f["code"].startswith(prefix) for f in vf) and text not in conds:
            conds.append(text)
    L += ["## 8. Required follow-up", "", "Conditions precedent (each tied to a verified finding):"]
    L += [f"- {c}" for c in conds] if conds else ["- None triggered by verified findings."]
    if gaps:
        L += ["", "Information requests (evidence categories with insufficient evidence):"]
        L += [f"- {k['label']} ({a.replace('_', ' ')}): {k['basis']}" for a, k in gaps]
    if comp and not comp.get("lei"):
        L += ["", "- Verify the legal-entity identifier manually; the GLEIF match was not accepted automatically."]
    L.append("")

    # 9. methodology
    L += ["## 9. Methodology, assumptions and limitations", "",
          f"Score = 100 × (1 − e^(−T/{SCALE_K:g})), where T = Σ severity weight × verification factor over accepted "
          f"findings. Severity weights: {', '.join(f'{k} {v:g}' for k, v in SEVERITY_WEIGHT.items())}. Verification "
          f"factor: verified {STATUS_FACTOR['verified']}, supported interpretation {STATUS_FACTOR['supported']}; "
          "rejected findings count 0. Each finding's points = score × its weight ÷ T. Bands: "
          + "; ".join(f"< {lim} {lab}" if lim <= 100 else f"≥ 75 {lab}" for lim, lab in THRESHOLDS) + ".",
          "", "The score is a screening output of this methodology. It is not a probability of default, a credit rating "
          "or a calibrated model, and related findings (e.g. a maturity wall and the absence of a refinancing "
          "discussion) can both contribute.", ""]
    if d.get("breakdown"):
        L += ["| Workstream | Points (sum = overall score) |", "|---|---|"]
        L += [f"| {k} | {v} |" for k, v in sorted(d["breakdown"].items(), key=lambda kv: -kv[1])] + [""]

    # 10. sources
    if d.get("sources"):
        L += ["## 10. Sources", "", "| Source | Filing / accession | Filed | URL | Retrieved (UTC) | How obtained |",
              "|---|---|---|---|---|---|"]
        L += [f"| {SOURCE_NAME.get(s['source'], s['source'])} | {s.get('accession') or '—'} | {s.get('filing_date') or '—'} | {s['url']} | "
              f"{s['retrieved_at']} | {MODE_LABEL.get(s['mode'], s['mode'])} |" for s in d["sources"]] + [""]

    # 11. approval history
    ap = d["approval"]
    hist = d.get("history") or {}
    L += ["## 11. Approval history", "", "| Step | By | When (UTC) | Note |", "|---|---|---|---|",
          f"| Analysis run started | {hist.get('started_by') or '—'} | {run['created_at']} | — |"]
    if hist.get("submitted_at"):
        L.append(f"| Submitted for partner review | {hist.get('submitted_by') or '—'} | {hist['submitted_at']} | "
                 f"{hist.get('submission_note') or '—'} |")
    L += [f"| Approved | {ap['by']} | {ap['at']} | {ap.get('note') or '—'} |", "",
          "---", f"**Approved by:** {ap['by']} on {ap['at']} (UTC) · analysis version {run['version']} · "
          f"report version {ap['report_version']} · findings fingerprint `{ap['findings_sha256'][:16]}`",
          f"**Review note:** {ap.get('note') or '—'}", "",
          "*Generated by Vantage DD from the approved analysis version. Not investment advice.*"]
    return "\n".join(L)
