"""Convert an EDGAR (inline XBRL) HTML filing into normalised plain text and split it into 10-K
Items. The section texts are stored verbatim (after deterministic whitespace normalisation), so every
evidence excerpt can be located by character offsets and re-verified later."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass

ITEMS = [  # (item id, title, doc_type used by the agents)
    ("1", "Business", "business"), ("1A", "Risk Factors", "risk_factors"),
    ("1B", "Unresolved Staff Comments", "other"), ("1C", "Cybersecurity", "other"),
    ("2", "Properties", "other"), ("3", "Legal Proceedings", "legal"), ("4", "Mine Safety Disclosures", "other"),
    ("5", "Market for Registrant's Common Equity", "other"), ("6", "Reserved", "other"),
    ("7", "Management's Discussion and Analysis", "management"), ("7A", "Quantitative and Qualitative Disclosures About Market Risk", "management"),
    ("8", "Financial Statements and Supplementary Data", "financial_notes"),
    ("9", "Changes in and Disagreements with Accountants", "other"), ("9A", "Controls and Procedures", "controls"),
    ("9B", "Other Information", "other"), ("9C", "Disclosure Regarding Foreign Jurisdictions", "other"),
    ("10", "Directors, Executive Officers and Corporate Governance", "other"),
    ("11", "Executive Compensation", "other"), ("12", "Security Ownership", "other"),
    ("13", "Certain Relationships and Related Transactions", "other"), ("14", "Principal Accountant Fees", "other"),
    ("15", "Exhibits and Financial Statement Schedules", "other"), ("16", "Form 10-K Summary", "other"),
]
KEEP_TYPES = {"business", "risk_factors", "legal", "management", "financial_notes", "controls"}


def html_to_text(raw: str) -> str:
    s = re.sub(r"<ix:header>.*?</ix:header>", " ", raw, flags=re.S | re.I)
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"</(p|div|tr|li|h\d|table)\s*>|<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</t[dh]\s*>", " | ", s, flags=re.I)
    # inline tags (span/font/b/i/a/ix:*) are removed without a space so words split across tags stay
    # whole; any other tag becomes a space
    s = re.sub(r"</?(span|font|b|i|u|a|em|strong|sup|sub|ix:[a-z]+)\b[^>]*>", "", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    lines = [ln.strip(" |") .strip() for ln in s.split("\n")]
    s = "\n".join(ln for ln in lines if ln)
    s = re.sub(r"\$ (\d)", r"$\1", s)
    s = re.sub(r"(\d) %", r"\1%", s)
    s = re.sub(r"\( (\d)", r"(\1", s)
    s = re.sub(r"(\d) \)", r"\1)", s)
    return s


@dataclass
class Section:
    item: str
    title: str
    doc_type: str
    start: int   # offset in the full normalised filing text
    text: str


_HEAD = re.compile(r"^\s*Item\s*(\d{1,2}[A-C]?)\s*[.:\-–—]?\s*(.{0,200})$", re.I | re.M)


def split_items(text: str) -> list[Section]:
    """Pick, for each Item heading, the occurrence that starts the longest body (the table of contents
    produces short-lived duplicates)."""
    known = {i: (t, d) for i, t, d in ITEMS}
    heads = [(m.start(), m.group(1).upper()) for m in _HEAD.finditer(text) if m.group(1).upper() in known]
    if not heads:
        return [Section("full", "Full filing", "other", 0, text)]
    heads.append((len(text), "_END"))
    spans: dict[str, tuple[int, int]] = {}
    for (pos, item), (nxt, _) in zip(heads, heads[1:], strict=False):
        length = nxt - pos
        if item not in spans or length > spans[item][1] - spans[item][0]:
            spans[item] = (pos, nxt)
    out = []
    for item, (a, b) in sorted(spans.items(), key=lambda kv: kv[1][0]):
        title, dtype = known[item]
        out.append(Section(item, title, dtype, a, text[a:b]))
    return out


def locate(haystack: str, excerpt: str) -> tuple[int, int] | None:
    i = haystack.find(excerpt)
    return (i, i + len(excerpt)) if i >= 0 else None
