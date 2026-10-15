"""Independent reconciliation of every verified-real company's four fiscal years of figures against SEC sources.

Independent of the application's own code path:
  * XBRL values come LIVE from SEC's per-concept endpoint (api/xbrl/companyconcept), not from the companyfacts
    file the app uses, and are selected here with this script's own rules (10-K/10-K/A, fiscal-year duration or
    instant, filed on or before the historical cut-off, latest such filing).
  * The original 10-K HTML is parsed with this script's own tag stripper and searched for the printed number.
  * Every derived metric is recomputed here with Decimal arithmetic from the independent values.
These are compared with what the running application serves (/api/v1/deals/{id}/financials) on a temporary DB.
Also checked: units (USD -> USD millions), signs, half-up display rounding, source filing URL and accession,
historical cut-off. Writes docs/evidence/sec_independent_reconciliation.md; exits 1 on any discrepancy.

    set VANTAGE_SEC_USER_AGENT=Your Name you@domain      (required: SEC fair-access policy)
    python scripts/independent_sec_reconciliation.py
    python scripts/independent_sec_reconciliation.py --self-test   # corrupts one value; must report it
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import tempfile
import time
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import httpx


def check(cond: object, msg: object = "verification check failed") -> None:
    """Explicit check (unlike `assert`, never removed by `python -O`): a verification script must not pass silently."""
    if not cond:
        raise SystemExit(f"CHECK FAILED: {msg}")


ROOT = Path(__file__).resolve().parents[1]
UA = os.getenv("VANTAGE_SEC_USER_AGENT")
if not UA:
    sys.exit("Set VANTAGE_SEC_USER_AGENT ('Name email') — SEC requires it for live access.")
tmp = Path(tempfile.mkdtemp(prefix="vantage-indep-"))
os.environ.update({"VANTAGE_ENV": "test", "VANTAGE_DEMO_MODE": "true", "VANTAGE_SEED_PASSWORD": "Indep-Check#2026",
                   "VANTAGE_DATABASE_URL": f"sqlite:///{tmp / 'v.db'}", "VANTAGE_CHECKPOINT_DB": str(tmp / "cp.db"),
                   "VANTAGE_STORAGE_DIR": str(tmp / "st"), "VANTAGE_VECTOR_INDEX_DIR": str(tmp / "vec"),
                   "VANTAGE_MLFLOW_ENABLED": "false", "VANTAGE_SOURCE_MODE": "snapshot",
                   "VANTAGE_JWT_SECRET": "indep-secret-indep-secret-indep-1234", "MLFLOW_DISABLE_AGENT_HINT": "1"})
sys.path.insert(0, str(ROOT / "backend"))

SELF_TEST = "--self-test" in sys.argv
# cik: (deal-name prefix, historical cut-off = 10-K filing date, latest fiscal year)
COMPANIES = {"716006": ("Yellow", date(2023, 2, 9), 2022), "878927": ("Old Dominion", date(2023, 2, 22), 2022),
             "1592058": ("Party City", date(2022, 2, 28), 2021), "28823": ("Diebold Nixdorf", date(2023, 3, 16), 2022),
             "1177702": ("Saia", date(2023, 2, 23), 2022)}
INSTANT = {"total_debt", "cash", "current_assets", "current_liabilities", "receivables"}
_cache: dict[str, dict] = {}
LIVE_LOG: list[str] = []


def concept(cik: str, tag: str) -> dict | None:
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{int(cik):010d}/us-gaap/{tag}.json"
    if url not in _cache:
        time.sleep(0.15)                                   # well under SEC's 10 requests/second
        r = httpx.get(url, headers={"User-Agent": UA}, timeout=30)
        LIVE_LOG.append(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC  {r.status_code}  {url}")
        _cache[url] = r.json() if r.status_code == 200 else None
    return _cache[url]


def independent_value(cik: str, tags: list[str], fy: int, cutoff: date, instant: bool) -> tuple[Decimal | None, list]:
    """Sum of the given tags for fiscal year `fy` (Dec 31 year end), using only 10-K/10-K/A facts filed on or before
    the cut-off; the latest such filing per tag."""
    total, used = Decimal(0), []
    for tag in tags:
        c = concept(cik, tag)
        if not c:
            return None, used
        rows = []
        for f in c.get("units", {}).get("USD", []):
            if f.get("form") not in ("10-K", "10-K/A") or f.get("end") != f"{fy}-12-31":
                continue
            if date.fromisoformat(f["filed"]) > cutoff:
                continue
            if instant != ("start" not in f):
                continue
            if not instant:
                days = (date.fromisoformat(f["end"]) - date.fromisoformat(f["start"])).days
                if not 350 <= days <= 380:
                    continue
            rows.append(f)
        if not rows:
            return None, used
        best = max(rows, key=lambda f: (f["filed"], f["accn"]))
        total += Decimal(str(best["val"]))
        used.append(best)
    return total, used


def filing_text(url: str) -> str | None:
    m = json.loads((ROOT / "data" / "source_snapshots" / "manifest.json").read_text(encoding="utf-8"))["entries"].get(url)
    if not m:
        return None
    raw = (ROOT / "data" / "source_snapshots" / m[-1]["path"]).read_bytes().decode("utf-8", "replace")
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def printed(value_usd: Decimal, text: str) -> str | None:
    v = abs(value_usd)
    cands = [f"{int((v / 1000).to_integral_value(ROUND_HALF_UP)):,}",
             f"{(v / 1000000).quantize(Decimal('0.1'), ROUND_HALF_UP):,}"]
    for s in cands:
        if len(s.replace(",", "").replace(".", "")) >= 3 and re.search(rf"(?<![\d.,]){re.escape(s)}(?![\d]|,\d|\.\d)", text):
            return s
    return None


def half_up(x: Decimal, dp: int) -> Decimal:
    return x.quantize(Decimal(1).scaleb(-dp), ROUND_HALF_UP)


def main() -> int:
    from app.analytics.metrics import fmt
    from app.main import app
    from fastapi.testclient import TestClient
    rows, issues, derived_rows = [], [], []
    with TestClient(app):
        c = TestClient(app)
        check(c.post("/api/v1/auth/login", json={"email": "analyst@vantage.dev",
                                                  "password": os.environ["VANTAGE_SEED_PASSWORD"]}).status_code == 200)
        deals = c.get("/api/v1/deals").json()
        for cik, (prefix, cutoff, last_fy) in COMPANIES.items():
            YEARS = [last_fy - 3, last_fy - 2, last_fy - 1, last_fy]
            deal = next(d for d in deals if d["name"].startswith(prefix))
            check(deal["historical_cutoff"] == cutoff.isoformat(), deal["historical_cutoff"])
            api = {(f["metric"], f["fiscal_year"]): f for f in c.get(f"/api/v1/deals/{deal['id']}/financials").json()}
            if SELF_TEST and prefix == "Old Dominion":       # prove the checker catches a wrong value and its knock-on
                api[("capex", 2022)]["value"] += 0.2
                api[("free_cash_flow", 2022)]["value"] -= 0.2
            ind: dict[tuple[str, int], Decimal | None] = {}
            texts: dict[str, str | None] = {}
            for (metric, fy), f in sorted(api.items()):
                if f["kind"] != "reported" or fy not in YEARS:
                    continue
                if f["value"] is None:
                    ind[(metric, fy)] = None
                    rows.append(f"| {prefix} | FY{fy} | {metric} | n/a ({f['status']}) | — | — | — | — | missing in app; shown as n/a |")
                    continue
                tags = [t.replace("us-gaap:", "") for t in f["xbrl_tag"].split(" + ")]
                val, used = independent_value(cik, tags, fy, cutoff, metric in INSTANT)
                ind[(metric, fy)] = val
                acc_ok = bool(used) and f["accession"] in {u["accn"] for u in used}
                filed_ok = all(date.fromisoformat(u["filed"]) <= cutoff for u in used) and date.fromisoformat(f["filed"]) <= cutoff
                url_ok = bool(f.get("filing_url")) and f["accession"].replace("-", "") in f["filing_url"]
                if f["filing_url"] not in texts:
                    texts[f["filing_url"]] = filing_text(f["filing_url"]) if f.get("filing_url") else None
                txt = texts[f["filing_url"]]
                pr = printed(Decimal(str(f["value"])) * 1000000, txt) if txt else None
                if pr is None and len(tags) > 1 and txt:
                    # composite (sum of several tagged lines) whose total is not printed: EACH component must be
                    parts = [printed(Decimal(str(u["val"])), txt) for u in used]
                    pr = ("components " + " + ".join(parts)) if len(parts) == len(tags) and all(parts) else None
                eq = val is not None and abs(val / 1000000 - Decimal(str(f["value"]))) < Decimal("0.0000005")
                disp_ok = fmt(f["value"], f["unit"]) == (("-" if val < 0 else "") + f"${abs(half_up(val / 1000000, 1)):,}M" if val is not None else "")
                ok = eq and acc_ok and filed_ok and url_ok and pr is not None and disp_ok and f["unit"] == "USD_millions"
                if not ok:
                    issues.append(f"{prefix} FY{fy} {metric}: xbrl_eq={eq} accession={acc_ok} cutoff={filed_ok} url={url_ok} printed={pr} display={disp_ok}")
                rows.append(f"| {prefix} | FY{fy} | {metric} | {f['value']:,.3f} | {(val / 1000000) if val is not None else 'n/a':,.3f} | "
                            f"{f['accession']} ({f['filed']}) | {pr or 'NOT FOUND'} | {fmt(f['value'], f['unit'])} | {'OK' if ok else 'DISCREPANCY'} |")
            # derived metrics, recomputed independently (Decimal, $M)
            def g(m, y, ind=ind):
                v = ind.get((m, y))
                return None if v is None else v / 1000000
            for fy in YEARS:
                rev, oi, da, ie = g("revenue", fy), g("operating_income", fy), g("depreciation_amortization", fy), g("interest_expense", fy)
                debt, cash, ocf, capex = g("total_debt", fy), g("cash", fy), g("operating_cash_flow", fy), g("capex", fy)
                ni, ca, cl, rec = g("net_income", fy), g("current_assets", fy), g("current_liabilities", fy), g("receivables", fy)
                ebitda = oi + da if oi is not None and da is not None else None
                calc = {
                    "ebitda": ebitda,
                    "ebitda_margin_pct": ebitda / rev * 100 if ebitda is not None and rev else None,
                    "net_debt": debt - cash if debt is not None and cash is not None else None,
                    "net_leverage_x": (debt - cash) / ebitda if None not in (debt, cash, ebitda) and ebitda > 0 else None,
                    "gross_leverage_x": debt / ebitda if None not in (debt, ebitda) and ebitda > 0 else None,
                    "interest_coverage_x": ebitda / ie if ebitda is not None and ie and ie > 0 else None,
                    "free_cash_flow": ocf - capex if ocf is not None and capex is not None else None,
                    "net_margin_pct": ni / rev * 100 if ni is not None and rev else None,
                    "current_ratio_x": ca / cl if ca is not None and cl else None,
                    "dso_days": rec / rev * 365 if rec is not None and rev else None,
                    "cash_conversion_x": ocf / ni if ocf is not None and ni and ni > 0 else None,
                }
                prev = g("revenue", fy - 1)
                calc["revenue_growth_pct"] = (rev / prev - 1) * 100 if rev is not None and prev and prev > 0 else None
                pc = g("cash", fy - 1)
                calc["cash_change_pct"] = (cash / pc - 1) * 100 if cash is not None and pc and pc > 0 else None
                for m, v in calc.items():
                    a = api.get((m, fy))
                    av = a["value"] if a else None
                    if v is None and av is None:
                        continue
                    same = v is not None and av is not None and abs(Decimal(str(av)) - v) < Decimal("0.000001")
                    if capex is not None and capex < 0:
                        issues.append(f"{prefix} FY{fy}: capex stored negative (sign convention)")
                    if not same:
                        issues.append(f"{prefix} FY{fy} {m}: app={av} independent={v}")
                    derived_rows.append(f"| {prefix} | FY{fy} | {m} | {av if av is None else fmt(av, a['unit'])} | "
                                        f"{'n/a' if v is None else f'{float(v):,.4f}'} | {'OK' if same else 'DISCREPANCY'} |")
    md = ["# Independent SEC reconciliation — all verified-real companies, four fiscal years each", "",
          f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `python scripts/independent_sec_reconciliation.py`.",
          "XBRL values were retrieved **live** from SEC `companyconcept` (a different endpoint from the app's stored "
          "`companyfacts` snapshot) and selected with this script's own rules; the original 10-K HTML was parsed "
          "independently; derived metrics were recomputed with Decimal arithmetic. Compared with the app's API on a temporary database.", "",
          f"**Result: {'PASS — no discrepancies' if not issues else f'{len(issues)} DISCREPANCIES'}**", "",
          "## Reported values", "",
          "| Company | FY | Metric | App ($M) | Independent XBRL ($M) | Source filing (filed) | Printed in 10-K | Display | Result |",
          "|---|---|---|---|---|---|---|---|---|", *rows, "",
          "## Derived values (recomputed independently)", "",
          "| Company | FY | Metric | App display | Independent value | Result |", "|---|---|---|---|---|---|", *derived_rows, "",
          "## Discrepancies", "", *([f"- {i}" for i in issues] or ["- None."]), "",
          "## Live requests made", "", "```", *LIVE_LOG, "```"]
    if SELF_TEST:
        caught = any("Old Dominion FY2022 capex" in i for i in issues)
        print("SELF-TEST:", "discrepancy detected as expected" if caught else "FAILED TO DETECT")
        return 0 if caught else 1
    out = ROOT / "docs" / "evidence" / "sec_independent_reconciliation.md"
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"reported rows {len(rows)}, derived rows {len(derived_rows)}, live requests {len(LIVE_LOG)}, discrepancies {len(issues)}")
    for i in issues[:30]:
        print("  ", i)
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
