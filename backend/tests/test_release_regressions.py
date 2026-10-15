"""Regression tests for the defects confirmed in the final release audit (reproduced first, then fixed):
R1 'Ready to submit' counted superseded drafts (runs) instead of deals whose LATEST version is a draft.
R2 a deal's last approved version was not distinguishable from its latest version.
R3 a superseded draft could still be submitted for review.
R4 the financial workstream's 'facts' count mixed reported facts with calculated values (98 vs 96/96).
R5 agent activity text contradicted the coverage record (e.g. 'Reviewed 0 market document(s)')."""
from __future__ import annotations

from .conftest import deal_by, submit, wait_run


def _run(sess, deal_id):
    return wait_run(sess, sess.post(f"/api/v1/deals/{deal_id}/runs", json={}).json()["id"])


def test_portfolio_counts_use_each_deals_latest_version(analyst, partner):
    y, o = deal_by(analyst, "Yellow")["id"], deal_by(analyst, "Old Dominion")["id"]
    # other real deals may hold drafts from earlier tests: count them separately
    def others_ready():
        return sum(1 for d in analyst.get("/api/v1/deals").json() if d["data_classification"] == "verified_real"
                   and d["id"] not in (y, o) and d["latest_status"] == "completed")
    # the user's sequence: Yellow v_a approved; ODFL v_b rejected; then new drafts for both; plus a 2nd ODFL draft
    ya = _run(analyst, y)
    submit(analyst, ya["id"])
    assert partner.post(f"/api/v1/runs/{ya['id']}/review", json={"decision": "approved", "note": "ok"}).status_code == 200
    ob = _run(analyst, o)
    submit(analyst, ob["id"])
    assert partner.post(f"/api/v1/runs/{ob['id']}/review",
                        json={"decision": "rejected", "note": "add an industry study"}).status_code == 200
    o_old, y_new, o_new = _run(analyst, o), _run(analyst, y), _run(analyst, o)

    g = analyst.get("/api/v1/portfolio/stats").json()["verified_real"]
    assert g["ready_to_submit"] == 2 + others_ready()      # R1: one per deal (Yellow, ODFL), not 3 runs
    deals = {d["id"]: d for d in analyst.get("/api/v1/deals").json()}
    assert deals[y]["latest_version"] == y_new["version"] and deals[y]["latest_status"] == "completed"
    assert deals[y]["approved_version"] == ya["version"]   # R2: the approval is still visible
    assert deals[y]["approved_run_id"] == ya["id"] and deals[y]["approved_risk_score"] == ya["risk_score"]
    approved_o = [r["version"] for r in analyst.get(f"/api/v1/deals/{o}/runs").json() if r["status"] == "approved"]
    assert deals[o]["latest_version"] == o_new["version"]
    assert deals[o]["approved_version"] == (max(approved_o) if approved_o else None)   # never the rejected/draft one
    detail = analyst.get(f"/api/v1/deals/{y}").json()
    assert detail["approved_version"] == ya["version"] and detail["latest_version"] == y_new["version"]
    # the approved memo stays readable while a newer draft exists
    assert partner.get(f"/api/v1/runs/{ya['id']}/report").status_code == 200
    # R3: the superseded ODFL draft cannot be submitted; the latest can
    r = analyst.post(f"/api/v1/runs/{o_old['id']}/submit", json={})
    assert r.status_code == 409 and "superseded" in r.text
    submit(analyst, o_new["id"])
    g = analyst.get("/api/v1/portfolio/stats").json()["verified_real"]
    assert g["ready_to_submit"] == 1 + others_ready() and g["awaiting_review"] >= 1


def test_reported_facts_and_calculated_values_are_counted_separately(analyst):
    deal = deal_by(analyst, "Yellow")
    run = _run(analyst, deal["id"])
    fin = next(c for c in run["coverage"] if c["agent"] == "financial_analyst")
    facts = analyst.get(f"/api/v1/deals/{deal['id']}/financials").json()
    reported = sum(1 for f in facts if f["kind"] == "reported" and f["value"] is not None)
    calculated = sum(1 for f in facts if f["kind"] == "calculated" and f["value"] is not None)
    assert fin["facts_used"] == reported == 48                  # R4: same definition as the 96/96 KPI (48 per company)
    assert fin["calculated_values"] == calculated and calculated > 0
    stats = analyst.get("/api/v1/portfolio/stats").json()["verified_real"]
    assert stats["reported_facts"] == 236 and "excludes calculated" in analyst.get("/api/v1/portfolio/stats").json()["definitions"]["reported_facts"]


def test_activity_messages_agree_with_coverage(analyst):
    deal = deal_by(analyst, "Old Dominion")
    run = _run(analyst, deal["id"])
    cov = {c["agent"]: c for c in run["coverage"]}
    ev = {e["agent"]: e["message"] for e in run["events"]}
    assert "Reviewed 0 independent market document(s) and 2 company description(s)" in ev["market_strategist"]
    assert cov["market_strategist"]["documents_reviewed"] == 2
    assert f"Scanned {cov['legal_counsel']['documents_reviewed']} document(s)" in ev["legal_counsel"]


def test_mcp_server_refuses_network_transport():
    """R6: the MCP server authenticates nobody (acts as one configured user), so it must never serve over HTTP."""
    import subprocess
    import sys
    from pathlib import Path
    backend = Path(__file__).resolve().parents[1]
    for flag in ("--http", "--sse", "--streamable-http"):
        r = subprocess.run([sys.executable, "-m", "mcp_server.server", flag], cwd=backend, capture_output=True,
                           text=True, encoding="utf-8", timeout=60, env={**__import__("os").environ, "PYTHONUTF8": "1"})
        assert r.returncode != 0 and "stdio only" in r.stderr, flag


def test_optional_deploy_files_have_no_hardcoded_credentials_or_scaling():
    """R7: container files must not ship default passwords, an unauthenticated MCP service, or >1 API replica."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "deploy" / "optional-container"
    compose = (root / "infra" / "docker-compose.yml").read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD: vantage" not in compose and "GF_SECURITY_ADMIN_PASSWORD: admin" not in compose
    assert "mcp_server.server --http" not in compose
    k8s = (root / "infra" / "k8s" / "deployment.yaml").read_text(encoding="utf-8")
    assert "replicas: 1" in k8s and "HorizontalPodAutoscaler" not in k8s.split("# No HorizontalPodAutoscaler")[0]
    render = (root / "render.yaml").read_text(encoding="utf-8")
    assert "value: prod" in render and "deploy/optional-container/Dockerfile" in render


def test_gross_and_net_leverage_are_distinct_and_correct(analyst, partner):
    """R10: gross leverage = total debt / EBITDA; net leverage = (total debt - cash) / EBITDA. Yellow FY2022:
    1,538.0 / 341.2 = 4.51x gross; 1,302.9 / 341.2 = 3.82x net. Both shown and labelled everywhere."""
    from app.analytics.metrics import fmt
    deal = deal_by(analyst, "Yellow")
    f = {(x["metric"], x["fiscal_year"]): x for x in analyst.get(f"/api/v1/deals/{deal['id']}/financials").json()}
    debt, cash, ebitda = f[("total_debt", 2022)]["value"], f[("cash", 2022)]["value"], f[("ebitda", 2022)]["value"]
    g, n = f[("gross_leverage_x", 2022)], f[("net_leverage_x", 2022)]
    assert abs(g["value"] - debt / ebitda) < 1e-12 and abs(n["value"] - (debt - cash) / ebitda) < 1e-12
    assert fmt(g["value"], "x") == "4.51x" and fmt(n["value"], "x") == "3.82x"
    assert g["formula"] == "total_debt / ebitda" and n["formula"] == "net_debt / ebitda"
    run = _run(analyst, deal["id"])
    lev = next(x for x in run["findings"] if x["code"] == "FIN.LEVERAGE_HIGH")
    assert lev["title"] == "Net leverage above credit comfort level" and lev["verification_status"] == "verified"
    assert "Net leverage (net debt / EBITDA) of 3.82x" in lev["detail"] and "gross leverage (total debt / EBITDA) is 4.51x" in lev["detail"]
    prof = next(x for x in run["findings"] if x["code"] == "FIN.PROFILE")
    assert "gross leverage (total debt/EBITDA) 4.51x" in prof["detail"] and "net leverage (net debt/EBITDA) 3.82x" in prof["detail"]
    submit(analyst, run["id"])
    assert partner.post(f"/api/v1/runs/{run['id']}/review", json={"decision": "approved", "note": "ok"}).status_code == 200
    md = partner.get(f"/api/v1/runs/{run['id']}/report").json()["content_md"]
    assert "| Gross leverage (total debt / EBITDA) |" in md and "| Net leverage (net debt / EBITDA) |" in md
    assert "4.51x" in md and "3.82x" in md
    odfl = deal_by(analyst, "Old Dominion")
    fo = {(x["metric"], x["fiscal_year"]): x for x in analyst.get(f"/api/v1/deals/{odfl['id']}/financials").json()}
    assert fmt(fo[("gross_leverage_x", 2022)]["value"], "x") == "0.05x" and fmt(fo[("net_leverage_x", 2022)]["value"], "x") == "-0.04x"


def test_historical_evidence_is_separated_from_current_metadata(analyst):
    """R11: sources are labelled by time basis relative to the cut-off; current identity metadata (GLEIF, submissions
    index) is never used in scoring, and no finding cites it."""
    deal = analyst.get(f"/api/v1/deals/{deal_by(analyst, 'Yellow')['id']}").json()
    assert deal["historical_cutoff"] == "2023-02-09"
    by = {}
    for s in deal["sources"]:
        by.setdefault(s["source"], []).append(s)
    assert all(s["time_basis"] == "current_metadata" and not s["used_in_scoring"] for s in by["gleif"] + by["sec_submissions"])
    assert all(s["time_basis"] == "historical" and s["used_in_scoring"] and s["filing_date"] <= "2023-02-09"
               for s in by["sec_filing"])
    assert all(s["time_basis"] == "point_in_time_filtered" for s in by["sec_companyfacts"] + by["fred"])
    assert not any(s["stale"] for s in by["sec_filing"])                     # historical documents do not go stale
    run = _run(analyst, deal["id"])
    cited = {e.get("source_url") or "" for f in run["findings"] for e in f["evidence"]}
    assert not any("gleif" in u or "/submissions/" in u for u in cited)
