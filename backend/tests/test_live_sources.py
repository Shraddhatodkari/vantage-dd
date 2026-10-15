"""REAL-SOURCE integration tests (network). Run with VANTAGE_LIVE_TESTS=1 and VANTAGE_SEC_USER_AGENT set.
They re-fetch the authoritative sources and check that the committed snapshot still matches them."""
import os

import pytest
from app.sources import fred, gleif, sec

pytestmark = pytest.mark.live


@pytest.fixture(autouse=True)
def _ua(monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "sec_user_agent",
                        os.getenv("VANTAGE_SEC_USER_AGENT", "Vantage DD tests admin@example.com"))


def test_sec_live_companyfacts_match_snapshot():
    live = sec.get_companyfacts("716006", mode="live").json()
    snap = sec.get_companyfacts("716006", mode="snapshot").json()
    from datetime import date
    ends = [date(2022, 12, 31)]
    a = {r["metric"]: r["value"] for r in sec.extract_annual_facts(live, ends, date(2023, 2, 9))}
    b = {r["metric"]: r["value"] for r in sec.extract_annual_facts(snap, ends, date(2023, 2, 9))}
    assert a == b and round(a["revenue"], 1) == 5244.7


def test_sec_live_submissions_find_yellow_fy2022_10k():
    r = sec.find_annual_report(sec.get_submissions("716006", mode="live").json(), 2022)
    assert r.accession == "0000950170-23-002332" and r.filing_date.isoformat() == "2023-02-09"


def test_gleif_live_lookup_exact_match():
    res, _ = gleif.lookup("Yellow Corporation", "DE", mode="live")
    assert res["match"] == "exact" and res["lei"] == "529900SEX4UQ2WLPRC40"


def test_fred_live_series():
    obs, _ = fred.get_series("FEDFUNDS", mode="live")
    d = dict(obs)
    from datetime import date
    assert d[date(2022, 12, 1)] == pytest.approx(4.10)
