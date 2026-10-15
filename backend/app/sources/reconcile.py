"""Reconcile each XBRL-reported fact with the human-readable text of the filing it came from.

The XBRL value (USD) is looked for in the 10-K text in the presentations filers actually use:
thousands ("1,691,582", ±1 for the filer's rounding), millions with one decimal ("1,691.6"), or whole
millions for values of 1,000M+ ("1,692"). Coincidental matches were measured on perturbed values (see tests). Negative values are matched on their absolute value
(filings print them in parentheses). The result is recorded per fact; nothing is ever assumed to match.

Status values:
  matched              the value is printed in the filing text (detail names the format)
  not_found            no presentation of the value was found — needs analyst review
  composite            value is a sum of several XBRL tags; the sum itself is not printed (each tag is)
  document_unavailable the filing document could not be retrieved
  not_checked          no reconciliation run yet / not applicable (calculated values)
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_NUM = r"(?<![\d.,]){}(?![\d]|,\d|\.\d)"


@dataclass
class Check:
    status: str
    detail: str
    passage: str | None = None      # the filing text around the printed value (label ... value)


def _variants(value_usd: float) -> list[tuple[str, str, int]]:
    """(printed form, label, max distance to the line-item label), most precise first. Thousands allow ±1 for
    the filer's rounding. Short numbers (3-digit thousands) need the label within 200 characters; millions are
    matched exactly (one decimal), and whole millions only for values of 1,000M+."""
    v = abs(value_usd)
    th = round(v / 1e3)
    out = [(f"{n:,}", "thousands", WINDOW if n >= 1000 else 200) for n in (th, th - 1, th + 1) if n >= 100]
    m1 = round(v / 1e5) / 10
    if m1 >= 10:
        out.append((f"{m1:,.1f}", "millions (1 dp)", WINDOW))
    m0 = round(v / 1e6)
    if m0 >= 1000:
        out.append((f"{m0:,}", "millions", WINDOW))
    return out


WINDOW = 450

# Line-item labels: a printed number only counts as evidence for a metric when one of its labels appears in
# the text shortly before it (statement tables print the label, then the values for each year).
LABELS: dict[str, str] = {
    "revenue": r"revenue|net sales",
    "operating_income": r"operating income|operating loss|operating profit|income from operations|\(loss\) from operations",
    "depreciation_amortization": r"depreciation",
    "interest_expense": r"interest expense",
    "net_income": r"net income|net loss|net \(loss\) income|net income \(loss\)",
    "operating_cash_flow": r"operating activities",
    "capex": r"property and equipment|capital expenditure|productive assets|property, plant",
    "total_debt": r"debt|borrowings|notes",
    "cash": r"cash and cash equivalents|cash, cash equivalents",
    "current_assets": r"total current assets",
    "current_liabilities": r"total current liabilities",
    "receivables": r"receivable",
}


def locate(value_usd: float, text: str, metric: str | None = None) -> tuple[str, str] | None:
    """(description, passage) of the first labelled occurrence of the value, or None. The passage runs from the
    nearest line-item label before the value to just after it, so a reader sees the actual filing line."""
    label = re.compile(LABELS[metric], re.I) if metric in LABELS else None
    for s, fmt, window in _variants(value_usd):
        for m in re.finditer(_NUM.format(re.escape(s)), text):
            if label is None:
                return f"{fmt}: '{s}'", text[max(0, m.start() - 120):m.end() + 20]
            lo = max(0, m.start() - window)
            labs = list(label.finditer(text, lo, m.start()))
            if labs:
                # start at the beginning of the line item (up to 80 characters before the label, word boundary)
                start = labs[-1].start()
                nl = text.rfind("\n", max(0, start - 80), start)
                start = nl + 1 if nl >= 0 else max(0, text.rfind(" ", max(0, start - 80), start) + 1)
                passage = " ".join(text[start:m.end() + 30].split())
                return f"{fmt}: '{s}' after its line-item label", passage[:400]
    return None


def find_in_text(value_usd: float, text: str, metric: str | None = None) -> str | None:
    """Description of the first labelled occurrence of the value, or None."""
    hit = locate(value_usd, text, metric)
    return hit[0] if hit else None


def check_fact(value_musd: float | None, xbrl_tag: str | None, text: str | None, metric: str | None = None) -> Check:
    if value_musd is None:
        return Check("not_checked", "no reported value")
    if text is None:
        return Check("document_unavailable", "filing document could not be retrieved")
    hit = locate(value_musd * 1e6, text, metric)
    if hit:
        return Check("matched", f"printed in filing text as {hit[0]}", hit[1])
    if xbrl_tag and " + " in xbrl_tag:
        return Check("composite", "sum of several XBRL tags; the total is not printed as one line in the filing")
    return Check("not_found", "value not found after its line-item label in the filing text (thousands or "
                              "millions) — review the filing")
