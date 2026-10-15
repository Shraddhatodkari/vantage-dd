"""Evidence model shared by all agents.

A finding's evidence is a list of typed items:
  document_excerpt  exact substring of a stored document + character locator (+ source URL / accession)
  reported_fact     a FinancialFact reported by a source (XBRL tag, accession, filing date) or an uploaded CSV
  calculation       a deterministic metric with formula and input values (re-computable)
  macro_series      observations from FRED with series id and retrieval metadata
  assumption        an explicit analyst assumption (e.g. a comfort threshold), always labelled as such
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from app.analytics.metrics import fmt
from app.db.models import Deal, Document, FinancialFact, MacroObservation, SourceRecord
from app.db.session import SessionLocal
from app.rag.ingest import load_document_text

COMPANYFACTS_PAGE = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


@dataclass
class Doc:
    id: str
    filename: str
    doc_type: str
    text: str
    source_url: str | None
    accession: str | None
    period_end: str | None
    classification: str
    filed: str | None = None          # filing date of the source document (look-ahead control)


@dataclass
class DealContext:
    deal: dict
    docs: list[Doc]
    facts: dict[tuple[str, int], dict] = field(default_factory=dict)
    macro: dict[str, list[dict]] = field(default_factory=dict)
    latest_year: int | None = None
    period_end: date | None = None
    cutoff: date | None = None        # historical cut-off: nothing filed/published after this date may be used

    def by_types(self, types: list[str]) -> list[Doc]:
        return [d for d in self.docs if d.doc_type in types]

    def fact(self, metric: str, year: int | None) -> dict | None:
        if year is None:
            return None
        f = self.facts.get((metric, year))
        return f if f and f["value"] is not None else None


def _fact_dict(f: FinancialFact, cik: str | None) -> dict:
    return {"id": f.id, "metric": f.metric, "fiscal_year": f.fiscal_year, "value": f.value, "unit": f.unit,
            "kind": f.kind, "status": f.status, "status_reason": f.status_reason, "xbrl_tag": f.xbrl_tag,
            "accession": f.accession, "form": f.form, "filed": f.filed.isoformat() if f.filed else None,
            "period_end": f.period_end.isoformat() if f.period_end else None, "formula": f.formula,
            "inputs": f.inputs, "source_document": f.source_document,
            "source_url": COMPANYFACTS_PAGE.format(cik=cik) if (cik and f.kind == "reported" and f.xbrl_tag) else None}


def load_context(deal_id: str) -> DealContext:
    with SessionLocal() as db:
        deal = db.get(Deal, deal_id)
        cik = deal.company.cik if deal.company else None
        docs = []
        for d in db.query(Document).filter_by(deal_id=deal_id).order_by(Document.uploaded_at).all():
            text = load_document_text(deal_id, d.id)
            if text is None:
                continue
            src = db.get(SourceRecord, d.source_record_id) if d.source_record_id else None
            docs.append(Doc(d.id, d.filename, d.doc_type, text, d.source_url, d.accession,
                            d.period_end.isoformat() if d.period_end else None, d.data_classification,
                            src.filing_date.isoformat() if src and src.filing_date else None))
        facts = {(f.metric, f.fiscal_year): _fact_dict(f, cik)
                 for f in db.query(FinancialFact).filter_by(deal_id=deal_id).all()}
        years = sorted({y for (m, y), f in facts.items() if f["kind"] == "reported" and f["value"] is not None})
        macro: dict[str, list[dict]] = {}
        mq = db.query(MacroObservation).order_by(MacroObservation.obs_date)
        if deal.historical_cutoff:   # never load observations dated after the cut-off
            mq = mq.filter(MacroObservation.obs_date <= deal.historical_cutoff)
        for o in mq.all():
            rec = db.get(SourceRecord, o.source_record_id)
            macro.setdefault(o.series_id, []).append(
                {"date": o.obs_date.isoformat(), "value": o.value, "source_url": rec.url if rec else None,
                 "retrieved_at": rec.retrieved_at.isoformat() if rec else None})
        info = {"id": deal.id, "name": deal.name, "target_company": deal.target_company, "deal_type": deal.deal_type,
                "sector": deal.sector, "classification": deal.data_classification,
                "period_end": deal.reporting_period_end.isoformat() if deal.reporting_period_end else None,
                "historical_cutoff": deal.historical_cutoff.isoformat() if deal.historical_cutoff else None}
        pe = deal.reporting_period_end or (date(years[-1], 12, 31) if years else None)
        return DealContext(info, docs, facts, macro, years[-1] if years else None, pe, deal.historical_cutoff)


# --------------------------------------------------------------------------- text search with offsets
_SENT_END = re.compile(r"(?<=[.;])\s+(?=[A-Z(\"“$])|\n")


def _sentence_bounds(text: str, pos: int) -> tuple[int, int]:
    start = 0
    for m in _SENT_END.finditer(text, max(0, pos - 1500), pos):
        start = m.end()
    m = _SENT_END.search(text, pos)
    end = m.start() if m else len(text)
    return start, end


def expand(text: str, a: int, b: int, min_len: int = 80, max_len: int = 600) -> tuple[int, int]:
    s, _ = _sentence_bounds(text, a)
    _, e = _sentence_bounds(text, max(a, b - 1))
    while e - s < min_len:  # short table cells: widen by whole lines
        ns = text.rfind("\n", 0, max(0, s - 1)) + 1
        ne = text.find("\n", e + 1)
        ne = len(text) if ne == -1 else ne
        if ns == s and ne == e:
            break
        s, e = ns, ne
    if e - s > max_len:  # centre a window on the match
        mid = (a + b) // 2
        s, e = max(s, mid - max_len // 2), min(e, mid + max_len // 2)
    return s, e


@dataclass
class Hit:
    doc: Doc
    match: re.Match
    start: int
    end: int

    @property
    def excerpt(self) -> str:
        return self.doc.text[self.start:self.end]


def find(docs: list[Doc], pattern: str, flags: int = re.I) -> Hit | None:
    rx = re.compile(pattern, flags)
    for d in docs:
        m = rx.search(d.text)
        if m:
            s, e = expand(d.text, m.start(), m.end())
            return Hit(d, m, s, e)
    return None


def find_all(docs: list[Doc], pattern: str, flags: int = re.I, limit: int = 20) -> list[Hit]:
    rx = re.compile(pattern, flags)
    out = []
    for d in docs:
        for m in rx.finditer(d.text):
            s, e = expand(d.text, m.start(), m.end())
            out.append(Hit(d, m, s, e))
            if len(out) >= limit:
                return out
    return out


# --------------------------------------------------------------------------- evidence builders
def ev_excerpt(h: Hit) -> dict:
    return {"kind": "document_excerpt", "document_id": h.doc.id, "filename": h.doc.filename,
            "doc_type": h.doc.doc_type, "source_url": h.doc.source_url, "accession": h.doc.accession,
            "filed": h.doc.filed,
            "period_end": h.doc.period_end, "classification": h.doc.classification, "excerpt": h.excerpt,
            "locator": {"start": h.start, "end": h.end}}


def ev_fact(f: dict) -> dict:
    kind = "calculation" if f["kind"] == "calculated" else "reported_fact"
    base = {"kind": kind, "fact_id": f["id"], "metric": f["metric"], "fiscal_year": f["fiscal_year"],
            "value": f["value"], "unit": f["unit"], "display": fmt(f["value"], f["unit"]),
            "period_end": f["period_end"]}
    if kind == "reported_fact":
        base.update({"xbrl_tag": f["xbrl_tag"], "accession": f["accession"], "form": f["form"], "filed": f["filed"],
                     "source_url": f["source_url"], "source_document": f["source_document"]})
    else:
        base.update({"formula": f["formula"], "inputs": f["inputs"]})
    return base


def ev_assumption(name: str, value: float, basis: str) -> dict:
    return {"kind": "assumption", "name": name, "value": value, "basis": basis}


def ev_count(name: str, n: int | float, basis: str) -> dict:
    """A count or simple derived number stated in a claim (e.g. number of provisions, years with losses)."""
    return {"kind": "calculation", "metric": name, "value": n, "unit": "count", "formula": basis, "inputs": []}


def ev_macro(series: str, points: list[dict]) -> dict:
    return {"kind": "macro_series", "series_id": series, "observations": points,
            "source_url": points[0]["source_url"] if points else None,
            "retrieved_at": points[0]["retrieved_at"] if points else None}


def finding(code: str, agent: str, category: str, severity: str, claim_type: str, title: str, detail: str,
            evidence: list[dict], limitations: str | None = None) -> dict:
    return {"code": code, "agent": agent, "category": category, "severity": severity, "claim_type": claim_type,
            "title": title, "detail": detail, "evidence": evidence, "limitations": limitations,
            "created_at": datetime.now(timezone.utc).isoformat()}
