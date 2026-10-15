"""SEC XBRL parsing: point-in-time selection, restatements, period validation, composite tags (mocked JSON)."""
from datetime import date

from app.sources.sec import extract_annual_facts, find_annual_report


def _fact(val, end, filed, accn, start=None, form="10-K"):
    f = {"val": val, "end": end, "filed": filed, "accn": accn, "form": form}
    if start:
        f["start"] = start
    return f


CF = {"facts": {"us-gaap": {
    "Revenues": {"units": {"USD": [
        _fact(100e6, "2022-12-31", "2023-02-10", "A1", "2022-01-01"),
        _fact(105e6, "2022-12-31", "2024-02-10", "A2", "2022-01-01"),          # later restatement
        _fact(30e6, "2022-12-31", "2023-02-10", "A1", "2022-10-01"),           # quarter: wrong duration
    ]}},
    "LongTermDebtNoncurrent": {"units": {"USD": [_fact(80e6, "2022-12-31", "2023-02-10", "A1")]}},
    "LongTermDebtCurrent": {"units": {"USD": [_fact(20e6, "2022-12-31", "2023-02-10", "A1")]}},
}}}


def test_point_in_time_value_and_restatement_flag():
    out = {(r["metric"], r["fiscal_year"]): r for r in extract_annual_facts(CF, [date(2022, 12, 31)], date(2023, 2, 10))}
    rev = out[("revenue", 2022)]
    assert rev["value"] == 100.0 and rev["accession"] == "A1"          # not the later 105
    assert rev["restated"] and "A2" in rev["restatement_note"]


def test_composite_debt_tag_and_missing_metrics():
    out = {(r["metric"], r["fiscal_year"]): r for r in extract_annual_facts(CF, [date(2022, 12, 31)], date(2023, 2, 10))}
    debt = out[("total_debt", 2022)]
    assert debt["value"] == 100.0 and "LongTermDebtNoncurrent + us-gaap:LongTermDebtCurrent" in debt["xbrl_tag"]
    cash = out[("cash", 2022)]
    assert cash["status"] == "missing" and cash["value"] is None


def test_facts_filed_after_as_of_date_are_ignored():
    out = {(r["metric"], r["fiscal_year"]): r for r in extract_annual_facts(CF, [date(2022, 12, 31)], date(2023, 1, 1))}
    assert out[("revenue", 2022)]["status"] == "missing"


def test_find_annual_report_prefers_original_and_lists_amendments():
    subs = {"cik": "716006", "filings": {"recent": {
        "accessionNumber": ["0001", "0002", "0003"], "form": ["10-K", "10-K/A", "10-Q"],
        "filingDate": ["2023-02-09", "2023-03-16", "2023-05-01"], "reportDate": ["2022-12-31", "2022-12-31", "2023-03-31"],
        "primaryDocument": ["a.htm", "b.htm", "c.htm"]}}}
    r = find_annual_report(subs, 2022)
    assert r.accession == "0001" and r.amendments == [{"accession": "0002", "filing_date": "2023-03-16"}]
    assert r.url.endswith("/716006/0001/a.htm")
