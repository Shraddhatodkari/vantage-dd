"""Portfolio KPIs, comparison, activity and fact drill-down: values must equal the underlying stored data."""
from __future__ import annotations

from .conftest import deal_by, submit, wait_run


def test_portfolio_kpis_come_from_stored_data(analyst):
    st = analyst.get("/api/v1/portfolio/stats").json()
    v = st["verified_real"]
    # 5 companies x 12 metrics x 4 years = 240 expected; Diebold does not tag capex (4 n/a) -> 236 reported.
    # 232 are printed in their filing; Diebold's 4 total-debt values are a sum of two printed lines (composite).
    assert v["deals"] == 5 and v["reported_facts"] == 236 and v["facts_confirmed_in_filing"] == 232 and v["facts_composite"] == 4
    assert v["sources"]["modes"] == ["snapshot"] and v["sources"]["count"] >= 30
    names = {d["name"] for d in v["deals_detail"]}
    assert names == {"Yellow Corporation — FY2022 credit review", "Old Dominion Freight Line — FY2022 credit review",
                     "Party City Holdco — FY2021 credit review", "Diebold Nixdorf — FY2022 credit review",
                     "Saia — FY2022 credit review"}
    assert all("illustrative" not in n.lower() for n in names)
    assert st["illustrative"]["reported_facts"] == 0 or st["illustrative"]["deals"] == 2   # kept separate
    assert "Not displayed" in st["definitions"]["avg_risk"]


def test_fact_drilldown_shows_filing_passage_and_link(analyst):
    deal = deal_by(analyst, "Old Dominion")
    facts = {(f["metric"], f["fiscal_year"]): f for f in analyst.get(f"/api/v1/deals/{deal['id']}/financials").json()}
    capex = facts[("capex", 2022)]
    assert "775,148" in capex["document_passage"] and capex["document_check"] == "matched"
    assert capex["filing_url"].endswith("odfl-20221231.htm")
    ie = facts[("interest_expense", 2019)]
    assert "377" in ie["document_passage"] and "nterest expense" in ie["document_passage"]
    assert ie["filing_url"].endswith("odfl-10k_20211231.htm")          # FY2019 value came from the FY2021 10-K
    assert facts[("free_cash_flow", 2022)]["filing_url"] is None        # calculated values have no filing


def test_compare_contains_only_verified_deals_and_matches_financials(analyst):
    rows = analyst.get("/api/v1/portfolio/compare").json()
    assert {r["company"] for r in rows} == {"Yellow Corporation", "OLD DOMINION FREIGHT LINE, INC.", "Party City Holdco Inc.",
                                             "Diebold Nixdorf, Incorporated", "Saia, Inc."}
    for r in rows:
        fin = {(f["metric"], f["fiscal_year"]): f["value"] for f in analyst.get(f"/api/v1/deals/{r['deal_id']}/financials").json()}
        for f in r["facts"]:
            assert fin[(f["metric"], f["fiscal_year"])] == f["value"]
        assert r["historical_cutoff"] in ("2023-02-09", "2023-02-22", "2022-02-28", "2023-03-16", "2023-02-23")
        assert r["sources_mode"] == ["snapshot"]


def test_activity_feed_records_submission(analyst):
    deal = deal_by(analyst, "Old Dominion")
    run = wait_run(analyst, analyst.post(f"/api/v1/deals/{deal['id']}/runs", json={}).json()["id"])
    submit(analyst, run["id"], "please review the coverage gap")
    acts = analyst.get("/api/v1/portfolio/activity").json()
    mine = [a for a in acts if a["deal_id"] == deal["id"] and a["version"] == run["version"]]
    assert {"analysis started", "analysis completed", "submitted for review"} <= {a["action"] for a in mine}
    assert any(a["by"] == "analyst@vantage.dev" and a["detail"] == "please review the coverage gap" for a in mine)


def test_dashboard_endpoints_respect_membership(admin, analyst):
    from app.api.routes_auth import login_limiter
    from fastapi.testclient import TestClient
    admin.post("/api/v1/admin/users", json={"email": "outsider3@vantage.dev", "full_name": "Out Sider",
                                            "password": "Outsider#Pass2026", "role": "analyst"})
    login_limiter.reset()
    out = TestClient(analyst.c.app)
    assert out.post("/api/v1/auth/login", json={"email": "outsider3@vantage.dev", "password": "Outsider#Pass2026"}).status_code == 200
    assert out.get("/api/v1/portfolio/compare").json() == []
    assert out.get("/api/v1/portfolio/activity").json() == []
    assert out.get("/api/v1/portfolio/stats").json()["verified_real"]["deals"] == 0
    assert admin.get("/api/v1/portfolio/compare").status_code == 403    # admin has no deal-content permission
