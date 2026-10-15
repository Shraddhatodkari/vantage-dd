"""SEC EDGAR: company submissions, XBRL company facts and filing documents.

Point-in-time rule: when analysing a fiscal year "as of" a given 10-K, only XBRL facts filed on or
before that 10-K's filing date are used. Later restatements are detected and reported, not silently
mixed in.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.sources.http import Retrieved, SourceUnavailable, fetch

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{doc}"

# Canonical metric -> ordered XBRL us-gaap tag candidates. First tag with a valid value wins.
DURATION_TAGS: dict[str, list] = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet"],
    "operating_income": ["OperatingIncomeLoss"],
    "depreciation_amortization": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
                                  "DepreciationAmortizationAndAccretionNet", "Depreciation"],
    "interest_expense": ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt",
                         "InterestAndDebtExpense"],   # e.g. Old Dominion tags its "Interest expense" line this way
    "net_income": ["NetIncomeLoss"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
}
INSTANT_TAGS: dict[str, list] = {
    # a tuple means "sum of these tags" (all must be reported for the period)
    "total_debt": ["LongTermDebt", "DebtLongtermAndShorttermCombinedAmount",
                   ("LongTermDebtNoncurrent", "LongTermDebtCurrent"),
                   ("LongTermDebtAndCapitalLeaseObligations", "LongTermDebtAndCapitalLeaseObligationsCurrent"),
                   ("LongTermDebtAndCapitalLeaseObligations", "NotesPayableCurrent")],
    # unrestricted cash first; the combined line only when the filer presents nothing else (labelled)
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "receivables": ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"],
}
# Metrics where the tags are alternative aggregates of different scope: use the MOST INCLUSIVE complete one (the
# largest), not the first. Example: Saia tags LongTermDebt = 0 (no notes outstanding) while its balance sheet
# carries $31.0M of finance-lease debt (LongTermDebtAndCapitalLeaseObligations + ...Current). For credit work the
# more inclusive measure is the conservative one. Ties keep list order.
MOST_INCLUSIVE = {"total_debt"}
# Shown with the value when a fallback tag with a different definition is used.
TAG_NOTES = {
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents":
        "Includes restricted cash: the filer reports only the combined line (no separate unrestricted cash tag).",
}


def pad_cik(cik: str | int) -> str:
    return str(int(cik)).zfill(10)


@dataclass
class AnnualReport:
    cik: str
    accession: str
    form: str
    filing_date: date
    report_date: date
    primary_document: str
    url: str
    amendments: list[dict] = field(default_factory=list)


def get_submissions(cik: str, mode: str | None = None) -> Retrieved:
    return fetch(SUBMISSIONS_URL.format(cik=pad_cik(cik)), "sec_submissions", mode=mode)


def get_companyfacts(cik: str, mode: str | None = None) -> Retrieved:
    return fetch(COMPANYFACTS_URL.format(cik=pad_cik(cik)), "sec_companyfacts", mode=mode)


def find_annual_report(subs: dict, fiscal_year: int) -> AnnualReport:
    """Locate the original 10-K whose period of report falls in `fiscal_year` and list any 10-K/A."""
    recent = subs["filings"]["recent"]
    rows = [dict(zip(recent.keys(), vals, strict=True)) for vals in zip(*recent.values(), strict=True)]
    tenk = [r for r in rows if r["form"] == "10-K" and r.get("reportDate", "").startswith(str(fiscal_year))]
    if not tenk:
        raise SourceUnavailable(f"No 10-K with period ending in {fiscal_year} found in SEC submissions "
                                "(older filings may be in paged submission files)")
    r = sorted(tenk, key=lambda x: x["filingDate"])[0]
    amends = [{"accession": a["accessionNumber"], "filing_date": a["filingDate"]} for a in rows
              if a["form"] == "10-K/A" and a.get("reportDate") == r["reportDate"]]
    cik_int = int(subs["cik"])
    url = ARCHIVE_URL.format(cik_int=cik_int, acc_nodash=r["accessionNumber"].replace("-", ""),
                             doc=r["primaryDocument"])
    return AnnualReport(pad_cik(subs["cik"]), r["accessionNumber"], r["form"], date.fromisoformat(r["filingDate"]),
                        date.fromisoformat(r["reportDate"]), r["primaryDocument"], url, amends)


def filing_for_accession(subs: dict, accession: str) -> AnnualReport:
    """Resolve any filing in the submissions index by accession number (used to reconcile each fact with
    the filing it actually came from)."""
    recent = subs["filings"]["recent"]
    for vals in zip(*recent.values(), strict=True):
        r = dict(zip(recent.keys(), vals, strict=True))
        if r["accessionNumber"] == accession:
            url = ARCHIVE_URL.format(cik_int=int(subs["cik"]), acc_nodash=accession.replace("-", ""),
                                     doc=r["primaryDocument"])
            return AnnualReport(pad_cik(subs["cik"]), accession, r["form"], date.fromisoformat(r["filingDate"]),
                                date.fromisoformat(r["reportDate"]), r["primaryDocument"], url)
    raise SourceUnavailable(f"accession {accession} not in the SEC submissions index")


def _valid_period(f: dict, fy_end: date, duration: bool) -> bool:
    if f.get("end") != fy_end.isoformat():
        return False
    if duration:
        if "start" not in f:
            return False
        days = (date.fromisoformat(f["end"]) - date.fromisoformat(f["start"])).days
        return 350 <= days <= 380
    return "start" not in f


def extract_annual_facts(companyfacts: dict, fy_ends: list[date], as_of_filed: date) -> list[dict]:
    """Return one record per (metric, fiscal year): value in USD millions, with tag, accession, form,
    filing date, and restatement information. Missing metrics are returned with status='missing'."""
    gaap = companyfacts.get("facts", {}).get("us-gaap", {})
    out = []
    for metric, tags, duration in ([(m, t, True) for m, t in DURATION_TAGS.items()]
                                   + [(m, t, False) for m, t in INSTANT_TAGS.items()]):
        for fy_end in fy_ends:
            rec = {"metric": metric, "fiscal_year": fy_end.year, "period_end": fy_end, "unit": "USD_millions",
                   "currency": "USD", "status": "missing", "value": None, "xbrl_tag": None,
                   "status_reason": f"none of {tags} reported for this period in filings up to {as_of_filed}"}
            options = []
            for tag in tags:
                parts = tag if isinstance(tag, tuple) else (tag,)
                picked = []
                for t in parts:
                    units = gaap.get(t, {}).get("units", {}).get("USD")
                    if not units:
                        break
                    cands = [f for f in units if f.get("form") in ("10-K", "10-K/A") and _valid_period(f, fy_end, duration)]
                    usable = [f for f in cands if date.fromisoformat(f["filed"]) <= as_of_filed]
                    if not usable:
                        break
                    chosen = sorted(usable, key=lambda f: (f["filed"], f["accn"]))[-1]
                    later = [f for f in cands if date.fromisoformat(f["filed"]) > as_of_filed
                             and abs(f["val"] - chosen["val"]) > max(1.0, abs(chosen["val"]) * 0.005)]
                    first = sorted(usable, key=lambda f: (f["filed"], f["accn"]))[0]
                    revised = (first if first["accn"] != chosen["accn"]
                               and abs(first["val"] - chosen["val"]) > max(1.0, abs(chosen["val"]) * 0.0005) else None)
                    picked.append((t, chosen, later, revised))
                if len(picked) != len(parts):
                    continue
                options.append(picked)
                if metric not in MOST_INCLUSIVE:
                    break
            if options:
                picked = max(options, key=lambda pk: sum(p[1]["val"] for p in pk)) if metric in MOST_INCLUSIVE \
                    else options[0]
                main = max((p[1] for p in picked), key=lambda f: (f["filed"], f["accn"]))
                later_all = [lt[-1] for _, _, lt, _ in picked if lt]
                revised_all = [(t, rv, ch) for t, ch, _, rv in picked if rv]
                rec.update({
                    "status": "ok", "value": sum(p[1]["val"] for p in picked) / 1e6,
                    "status_reason": " ".join(TAG_NOTES[t] for t, *_ in picked if t in TAG_NOTES) or None,
                    "xbrl_tag": " + ".join(f"us-gaap:{t}" for t, *_ in picked),
                    "accession": main["accn"], "form": main["form"], "filed": date.fromisoformat(main["filed"]),
                    "period_start": date.fromisoformat(main["start"]) if duration else None,
                    "restated": bool(later_all),
                    "restatement_note": ("Later filing(s) report different values: " + "; ".join(
                        f"{x['accn']} ({x['filed']}) {x['val'] / 1e6:.1f}" for x in later_all)
                        + " — point-in-time value kept") if later_all else None,
                    "revision_note": ("Revised before the cut-off: " + "; ".join(
                        f"{t} originally {rv['val'] / 1e6:,.1f} in {rv['accn']} ({rv['filed']}), "
                        f"{ch['val'] / 1e6:,.1f} in {ch['accn']} ({ch['filed']}) — latest value on or before "
                        f"{as_of_filed} used" for t, rv, ch in revised_all)) if revised_all else None,
                })
            out.append(rec)
    return out


def filing_document_url(report: AnnualReport) -> str:
    return report.url


def get_filing_document(report: AnnualReport, mode: str | None = None) -> Retrieved:
    return fetch(report.url, "sec_filing", mode=mode)
