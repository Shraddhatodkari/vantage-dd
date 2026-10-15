"""Reproducible source-to-screen verification for the verified-real deals (Yellow Corporation and Old Dominion
Freight Line, plus the blind-benchmark companies; four fiscal years each, as of each company's 10-K).

For every reported figure it checks, independently:
  1. the raw SEC XBRL value in the stored companyfacts snapshot (sha256-verified),
  2. that the value is printed (after its line-item label) in the text of the filing it came from,
  3. the value persisted in the database and returned by the API (/deals/{id}/financials),
  4. that the fact was filed on or before the historical cut-off,
  5. for FY2022 headline figures, that the formatted display appears in the approved IC memo.
Derived values are re-computed from their stored inputs. Writes docs/evidence/<company>_source_to_screen.md
and exits 1 on any mismatch. Runs entirely on a temporary database (never touches backend/vantage.db).

    python scripts/verify_source_to_screen.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
tmp = Path(tempfile.mkdtemp(prefix="vantage-verify-"))
os.environ.update({"VANTAGE_ENV": "test", "VANTAGE_DEMO_MODE": "true", "VANTAGE_SEED_PASSWORD": "Verify-Only#Pass2026",
                   "VANTAGE_DATABASE_URL": f"sqlite:///{tmp / 'v.db'}", "VANTAGE_CHECKPOINT_DB": str(tmp / "cp.db"),
                   "VANTAGE_STORAGE_DIR": str(tmp / "st"), "VANTAGE_VECTOR_INDEX_DIR": str(tmp / "vec"),
                   "VANTAGE_BACKUP_DIR": str(tmp / "bk"), "VANTAGE_LLM_PROVIDER": "offline",
                   "VANTAGE_MLFLOW_ENABLED": "false", "VANTAGE_SOURCE_MODE": "snapshot",
                   "VANTAGE_JWT_SECRET": "verify-secret-verify-secret-verify-1234", "MLFLOW_DISABLE_AGENT_HINT": "1"})
sys.path.insert(0, str(ROOT / "backend"))

from app.analytics.metrics import fmt, recompute  # noqa: E402
from app.main import app  # noqa: E402
from app.sources import reconcile, sec  # noqa: E402
from app.sources.filing_text import html_to_text  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def check(cond: object, msg: object = "verification check failed") -> None:
    """Explicit check (unlike `assert`, never removed by `python -O`): a verification script must not pass silently."""
    if not cond:
        raise SystemExit(f"CHECK FAILED: {msg}")


# (cik, deal-name prefix, evidence file slug, latest fiscal year of the 10-K used)
COMPANIES = [("716006", "Yellow", "yellow", 2022), ("878927", "Old Dominion", "odfl", 2022),
             ("1592058", "Party City", "party_city", 2021), ("28823", "Diebold Nixdorf", "diebold", 2022),
             ("1177702", "Saia", "saia", 2022)]


def component_hits(cf: dict, tags: list[str], fy_end: date, cutoff: date, text: str, metric: str) -> str | None:
    """For a composite value (sum of tags) whose total is not printed: every component must be printed."""
    gaap, out = cf["facts"]["us-gaap"], []
    for t in tags:
        rows = [f for f in gaap.get(t, {}).get("units", {}).get("USD", []) if f.get("form") in ("10-K", "10-K/A")
                and f.get("end") == fy_end.isoformat() and "start" not in f and f["filed"] <= cutoff.isoformat()]
        if not rows:
            return None
        v = max(rows, key=lambda f: (f["filed"], f["accn"]))["val"]
        hit = reconcile.find_in_text(v, text, metric)
        if not hit:
            return None
        out.append(f"{t} {v / 1e6:,.1f}")
    return "components printed: " + " + ".join(out)
MEMO_METRICS = ["revenue", "total_debt", "cash", "net_income", "capex", "operating_cash_flow"]
CALCS = ["ebitda", "net_debt", "gross_leverage_x", "net_leverage_x", "interest_coverage_x", "free_cash_flow", "ebitda_margin_pct",
         "cash_change_pct"]


def login(email: str) -> TestClient:
    s = TestClient(app)
    check(s.post("/api/v1/auth/login", json={"email": email, "password": os.environ["VANTAGE_SEED_PASSWORD"]}).status_code == 200)
    return s


def verify_company(cik: str, prefix: str, an: TestClient, pa: TestClient, last: int) -> tuple[list[str], bool, dict]:
    subs = sec.get_submissions(cik, "snapshot").json()
    rep = sec.find_annual_report(subs, last)
    cf = sec.get_companyfacts(cik, "snapshot")
    years = [date(y, 12, 31) for y in range(last - 3, last + 1)]
    raw = {(r["metric"], r["fiscal_year"]): r for r in sec.extract_annual_facts(cf.json(), years, rep.filing_date)}
    texts: dict[str, str] = {}
    deal = next(d for d in an.get("/api/v1/deals").json() if d["name"].startswith(prefix))
    detail = an.get(f"/api/v1/deals/{deal['id']}").json()
    api = {(f["metric"], f["fiscal_year"]): f for f in an.get(f"/api/v1/deals/{deal['id']}/financials").json()}
    h = {"X-CSRF-Token": an.cookies.get("vantage_csrf")}
    run_id = an.post(f"/api/v1/deals/{deal['id']}/runs", json={}, headers=h).json()["id"]
    for _ in range(400):
        run = an.get(f"/api/v1/runs/{run_id}").json()
        if run["status"] not in ("queued", "running"):
            break
        time.sleep(0.3)
    check(run["status"] == "completed", run["status"])
    r = an.post(f"/api/v1/runs/{run_id}/submit", json={"note": "submitted by verification script"}, headers=h)
    check(r.status_code == 200 and r.json()["status"] == "awaiting_review", r.text)
    hp = {"X-CSRF-Token": pa.cookies.get("vantage_csrf")}
    r = pa.post(f"/api/v1/runs/{run_id}/review", json={"decision": "approved", "note": "source-to-screen verification"},
                headers=hp)
    check(r.status_code == 200, r.text)
    memo = pa.get(f"/api/v1/runs/{run_id}/report").json()["content_md"]
    ok, rows, stats = True, [], {"reported": 0, "matched": 0, "missing": 0}
    cutoff = rep.filing_date
    for (metric, fy), rr in sorted(raw.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        f = api.get((metric, fy))
        if rr["status"] != "ok":
            stats["missing"] += 1
            shown = f and f["value"] is None
            ok &= bool(shown)
            rows.append(f"| FY{fy} | {metric} | — | missing in XBRL up to {cutoff} | — | — | "
                        f"{'n/a (shown as missing)' if shown else 'NOT SHOWN AS MISSING'} | — | {'PASS' if shown else 'FAIL'} |")
            continue
        stats["reported"] += 1
        if rr["accession"] not in texts:
            doc = sec.get_filing_document(sec.filing_for_accession(subs, rr["accession"]), "snapshot")
            texts[rr["accession"]] = html_to_text(doc.text())
        hit = reconcile.find_in_text(rr["value"] * 1e6, texts[rr["accession"]], metric)
        stats["matched"] += hit is not None
        composite = None
        if hit is None and " + " in (rr["xbrl_tag"] or ""):
            composite = component_hits(cf.json(), [t.replace("us-gaap:", "") for t in rr["xbrl_tag"].split(" + ")],
                                       date(fy, 12, 31), cutoff, texts[rr["accession"]], metric)
            stats["composite"] = stats.get("composite", 0) + (composite is not None)
        disp = fmt(f["value"], f["unit"])
        in_memo = disp in memo if (fy == last and metric in MEMO_METRICS) else None
        checks = {"api_eq_xbrl": abs(rr["value"] - f["value"]) < 1e-9, "in_filing": hit is not None or composite is not None,
                  "accession": f["accession"] == rr["accession"], "cutoff": rr["filed"] <= cutoff,
                  "db_check": f.get("document_check") == ("matched" if hit else "composite"), "memo": in_memo is not False}
        good = all(checks.values())
        ok &= good
        rows.append(f"| FY{fy} | {metric} | {rr['xbrl_tag'].replace('us-gaap:', '')} | {rr['accession']} (filed {rr['filed']}) | "
                    f"{rr['value']:,.3f} | {hit or composite or 'NOT FOUND'} | {disp} | "
                    f"{'yes' if in_memo else ('NO' if in_memo is False else '—')} | {'PASS' if good else 'FAIL'} |")
    calc_rows = []
    for m in CALCS:
        f = api.get((m, last))
        if not f or f["value"] is None:
            calc_rows.append(f"| {m} | n/a | {(f or {}).get('status_reason') or 'input missing'} | n/a | — |")
            continue
        rv = recompute({"metric": m, "inputs": f["inputs"]})
        good = rv is not None and abs(rv - f["value"]) < 1e-9
        ok &= good
        ins = "; ".join(f"{i['metric']} FY{i['fiscal_year']}={i['value']:,.3f}" for i in f["inputs"])
        calc_rows.append(f"| {m} | `{f['formula']}` | {ins} | {fmt(f['value'], f['unit'])} (exact {f['value']:,.4f}) | "
                         f"{'PASS' if good else 'FAIL'} |")
    cov = run.get("coverage") or []
    md = [f"# {detail['target_company']} — FY{last - 3}–FY{last} source-to-screen verification", "",
          f"Generated by `python scripts/verify_source_to_screen.py` on a temporary database. Analysis as of Form 10-K "
          f"{rep.accession} filed {rep.filing_date} (historical cut-off). XBRL from the SEC companyfacts stored snapshot "
          f"(sha256 `{cf.sha256[:16]}…`, retrieved {cf.retrieved_at.isoformat()}; **stored snapshot, not live**).", "",
          f"Reported values: {stats['reported']}, printed in their own filing: {stats['matched']}, composite (each "
          f"component printed): {stats.get('composite', 0)}, "
          f"missing in XBRL (shown as n/a, never 0): {stats['missing']}.", "",
          "| FY | Metric | XBRL tag | Source filing | XBRL ($M) | Found in filing text | Screen display | In approved memo | Result |",
          "|---|---|---|---|---|---|---|---|---|", *rows, "",
          f"## Derived values (FY{last}), re-computed from stored inputs at full precision", "",
          "| Metric | Formula | Inputs ($M, unrounded) | Display | Result |", "|---|---|---|---|---|", *calc_rows, "",
          "Display rounding: each figure is rounded half-up independently, so rounded inputs may not add up exactly to a "
          "rounded result (e.g. 1,691.6 − 775.1 = 916.5, while the exact 1,691.582 − 775.148 = 916.434 → $916.4M).", "",
          f"## Analysis run (offline rules, methodology {run['methodology_version']})", "",
          f"Risk score {run['risk_score']}/100 → {run['recommendation']}; approved by partner@vantage.dev in this "
          "verification only.", "",
          "| Workstream | Docs reviewed | Reported facts | Calculated values | Rules | Matches | Findings | LLM | Limitation |", "|---|---|---|---|---|---|---|---|---|",
          *[f"| {c['agent']} | {c['documents_reviewed']} | {c['facts_used']} | {c.get('calculated_values', 0)} | {c['rules_evaluated']} | {c['rule_matches']} | "
            f"{c['candidate_findings']} | {c['llm']} | {c.get('limitation') or '—'} |" for c in cov], "",
          f"Overall: **{'PASS' if ok else 'FAIL'}**"]
    return md, ok, {"risk": run["risk_score"], "rec": run["recommendation"], **stats}


def main() -> int:
    all_ok, summary = True, []
    with TestClient(app):
        an, pa = login("analyst@vantage.dev"), login("partner@vantage.dev")
        for cik, prefix, slug, last in COMPANIES:
            md, ok, st = verify_company(cik, prefix, an, pa, last)
            out = ROOT / "docs" / "evidence" / f"{slug}_source_to_screen.md"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("\n".join(md) + "\n", encoding="utf-8")
            all_ok &= ok
            summary.append(f"{prefix}: {'PASS' if ok else 'FAIL'} — {st}")
    print("\n".join(summary))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
