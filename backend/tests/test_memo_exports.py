"""IC memo content, consistency with the approved run, score contributions, strengths and export formats."""
from __future__ import annotations

import hashlib
import re

from app.api.routes_deals import render_memo_html

from .conftest import deal_by, submit, wait_run


def _approved(analyst, partner, name):
    deal = deal_by(analyst, name)
    run = wait_run(analyst, analyst.post(f"/api/v1/deals/{deal['id']}/runs", json={}).json()["id"])
    submit(analyst, run["id"], "Coverage checked; market study missing.")
    r = partner.post(f"/api/v1/runs/{run['id']}/review", json={"decision": "approved", "note": "Approved — historical case."})
    assert r.status_code == 200, r.text
    return r.json(), partner.get(f"/api/v1/runs/{run['id']}/report").json()


def test_memo_sections_and_consistency_with_approved_run(analyst, partner):
    run, rep = _approved(analyst, partner, "Yellow")
    md = rep["content_md"]
    for h in ["## 1. Executive summary", "## 2. Credit thesis — positive evidence", "## 3. Material risks",
              "## 4. Financial trends and ratios", "## 5. Debt maturities and covenant observations",
              "## 6. Detailed findings with evidence", "## 7. Evidence coverage and unresolved questions",
              "## 8. Required follow-up", "## 9. Methodology, assumptions and limitations", "## 10. Sources",
              "## 11. Approval history"]:
        assert h in md, h
    assert f"risk score {run['risk_score']}/100" in md and run["recommendation"] in md
    accepted = [f for f in run["findings"] if f["verification_status"] != "rejected"]
    assert all(f["title"] in md for f in accepted)
    # every finding's score points shown in the memo equal the API's points
    for f in accepted:
        if f["severity"] != "low":
            assert re.search(rf"\| {re.escape(f['title'])} \|[^\n]*\| {f['score_points']} \|", md), f["title"]
    assert "not a probability of default" in md
    assert "Submitted for partner review | analyst@vantage.dev" in md and "Approved | partner@vantage.dev" in md
    assert "0000950170-23-002332 | 2023-02-09" in md                      # source with filing date
    assert "FRED (St. Louis Fed)" in md and "stored snapshot" in md
    assert "$1,538.0M" in md and "-$70.5M" in md and "3.82x" in md and "2.09x" in md
    assert "Independent market or industry study" in md                  # disclosed gap


def test_score_points_sum_to_score(analyst):
    deal = deal_by(analyst, "Yellow")
    run = wait_run(analyst, analyst.post(f"/api/v1/deals/{deal['id']}/runs", json={}).json()["id"])
    pts = [f["score_points"] for f in run["findings"] if f["verification_status"] != "rejected"]
    assert abs(sum(pts) - run["risk_score"]) <= 0.05 * len(pts)          # each rounded to 0.1
    assert all(f["score_points"] == 0 for f in run["findings"] if f["verification_status"] == "rejected")


def test_strengths_are_fact_based(analyst, partner):
    _, odfl = _approved(analyst, partner, "Old Dominion")
    md = odfl["content_md"]
    assert "Net cash position of $86.3M" in md and "Positive free cash flow of $916.4M" in md
    assert "1,354x" in md and "2,844.53x" not in md                     # no false precision on large ratios
    yellow_md = _approved(analyst, partner, "Yellow")[1]["content_md"]
    thesis = yellow_md.split("## 2. Credit thesis")[1].split("## 3.")[0]
    assert "Positive free cash flow" not in thesis and "below the 3.5x" not in thesis


def test_html_export_matches_markdown_and_is_safe(analyst, partner):
    run, rep = _approved(analyst, partner, "Old Dominion")
    r = partner.get(f"/api/v1/runs/{run['id']}/report.html")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert r.headers["x-content-sha256"] == rep["content_sha256"] == hashlib.sha256(rep["content_md"].encode()).hexdigest()
    html = r.text
    assert "<table>" in html and "Executive summary" in html and "$916.4M" in html and "<script" not in html
    md = partner.get(f"/api/v1/runs/{run['id']}/report.md")
    assert md.text == rep["content_md"]
    # same approved version re-exported -> identical bytes (reproducible)
    assert partner.get(f"/api/v1/runs/{run['id']}/report.html").text == html


def test_html_render_neutralises_embedded_markup():
    out = render_memo_html('> quote: <script>alert(1)</script> & <img src=x onerror=1>\n\n| a |\n|---|\n| <b>x</b> |', "s", 1)
    assert "<script>" not in out and "<img" not in out and "<b>" not in out
    assert "&lt;script&gt;" in out or "&lt;script>" in out
