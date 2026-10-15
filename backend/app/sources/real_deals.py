"""Build or refresh a verified-real deal from authoritative sources:
SEC submissions + XBRL company facts + the 10-K document, GLEIF LEI, FRED macro series.

Idempotent: re-running with unchanged sources changes nothing; changed sources add new document
versions and update facts, and every change is audited. Approved analyses are never modified
(their findings and memo are stored immutably)."""
from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from app.analytics.financials import materialize_calculations
from app.db.models import (
    Company,
    Deal,
    DealMember,
    Document,
    FinancialFact,
    MacroObservation,
    SourceRecord,
)
from app.rag.ingest import ingest_text
from app.sources import fred, gleif, reconcile, sec
from app.sources.filing_text import KEEP_TYPES, html_to_text, split_items
from app.sources.http import Retrieved, SourceUnavailable

log = logging.getLogger("vantage.real_deals")
MACRO_SERIES = ["FEDFUNDS"]


@dataclass
class BuildReport:
    deal_id: str
    company: str
    accession: str
    sources: list[dict] = field(default_factory=list)
    facts_written: int = 0
    facts_missing: list[str] = field(default_factory=list)
    restated: list[str] = field(default_factory=list)
    documents_added: int = 0
    documents_unchanged: int = 0
    warnings: list[str] = field(default_factory=list)


def _record(db: Session, r: Retrieved, *, company_id: str | None = None, accession: str | None = None,
            form: str | None = None, filing_date: date | None = None, period_end: date | None = None,
            notes: str | None = None) -> SourceRecord:
    existing = db.query(SourceRecord).filter_by(url=r.url, sha256=r.sha256).first()
    if existing:
        return existing
    rec = SourceRecord(source=r.source, url=r.url, company_id=company_id, accession=accession, form=form,
                       filing_date=filing_date, period_end=period_end, retrieved_at=r.retrieved_at,
                       retrieval_mode=r.mode, sha256=r.sha256, bytes=len(r.content),
                       local_path=str(r.local_path.name), notes=notes)
    db.add(rec)
    db.flush()
    return rec


def _reconcile_with_filings(db: Session, deal: Deal, subs: dict, company_id: str, mode: str | None,
                            build: BuildReport) -> None:
    """Check every reported fact against the text of the filing (accession) it was taken from."""
    texts: dict[str, str | None] = {}
    for f in db.query(FinancialFact).filter_by(deal_id=deal.id, kind="reported"):
        if f.value is None or not f.accession:
            f.document_check, f.document_check_detail = "not_checked", "no reported value"
            continue
        if f.accession not in texts:
            try:
                rep = sec.filing_for_accession(subs, f.accession)
                r = sec.get_filing_document(rep, mode)
                _record(db, r, company_id=company_id, accession=rep.accession, form=rep.form,
                        filing_date=rep.filing_date, period_end=rep.report_date,
                        notes="Filing document used to reconcile reported XBRL facts")
                texts[f.accession] = html_to_text(r.text())
            except SourceUnavailable as exc:
                texts[f.accession] = None
                build.warnings.append(f"reconciliation: filing {f.accession} unavailable ({exc})")
        chk = reconcile.check_fact(f.value, f.xbrl_tag, texts[f.accession], f.metric)
        f.document_check, f.document_check_detail = chk.status, chk.detail[:400]
        f.document_passage = chk.passage
        if chk.status in ("not_found", "document_unavailable"):
            build.warnings.append(f"reconciliation {chk.status}: {f.metric} FY{f.fiscal_year} ({f.accession})")
    db.flush()


def build_real_deal(db: Session, *, cik: str, fiscal_year: int, name: str, deal_type: str, sector: str,
                    owner_id: str, member_ids: list[str] | None = None, mode: str | None = None) -> BuildReport:
    subs_r = sec.get_submissions(cik, mode)
    subs = subs_r.json()
    report = sec.find_annual_report(subs, fiscal_year)
    cf_r = sec.get_companyfacts(cik, mode)
    cf = cf_r.json()

    company = db.query(Company).filter_by(cik=sec.pad_cik(cik)).first() or Company(cik=sec.pad_cik(cik), name="")
    company.name = cf.get("entityName") or subs.get("name")
    company.tickers = subs.get("tickers", [])
    company.sic, company.sic_description = subs.get("sic"), subs.get("sicDescription")
    company.fiscal_year_end = subs.get("fiscalYearEnd")
    company.state_of_incorporation = subs.get("stateOfIncorporation")
    db.add(company)
    db.flush()

    out_sources = []
    _record(db, subs_r, company_id=company.id, notes="SEC submissions index")
    rec_cf = _record(db, cf_r, company_id=company.id, notes="SEC XBRL company facts")

    # ---- GLEIF identity check (never guessed)
    try:
        lei, lei_r = gleif.lookup(company.name, company.state_of_incorporation, mode)
        _record(db, lei_r, company_id=company.id, notes=f"GLEIF lookup: {lei['match']}")
        company.lei_match = lei["match"]
        if lei["match"] == "exact":
            company.lei, company.lei_legal_name = lei["lei"], lei["legal_name"]
            company.lei_status = f"{lei['entity_status']} entity / {lei['registration_status']} registration"
        company.lei_record = lei
        out_sources.append({"source": "GLEIF", "url": lei_r.url, "retrieved_at": lei_r.retrieved_at.isoformat(),
                            "mode": lei_r.mode})
    except SourceUnavailable as exc:
        company.lei_match = "unavailable"
        out_sources.append({"source": "GLEIF", "error": str(exc)})

    deal = db.query(Deal).filter_by(company_id=company.id, reporting_period_end=report.report_date).first()
    if deal is None:
        deal = Deal(id=uuid.uuid4().hex, name=name, target_company=company.name, company_id=company.id,
                    deal_type=deal_type, sector=sector, data_classification="verified_real",
                    reporting_period_end=report.report_date, owner_id=owner_id, currency="USD")
        db.add(deal)
        db.flush()
    deal.is_historical = (date.today() - report.report_date).days > 400
    # Historical cut-off: the analysis may only use information filed/published on or before the 10-K filing date.
    deal.historical_cutoff = report.filing_date
    if company.lei_match == "exact" and company.lei_legal_name:
        # prefer the GLEIF-registered legal name casing for display; SEC entity name kept on the company record
        deal.target_company = company.lei_legal_name if not company.lei_legal_name.isupper() else company.name
    for uid in {owner_id, *(member_ids or [])}:
        if not db.query(DealMember).filter_by(deal_id=deal.id, user_id=uid).first():
            db.add(DealMember(deal_id=deal.id, user_id=uid, added_by=owner_id))

    build = BuildReport(deal.id, company.name, report.accession)

    # ---- XBRL facts, point-in-time as of the 10-K filing date
    fy_ends = [date(report.report_date.year - k, report.report_date.month, report.report_date.day)
               for k in range(3, -1, -1)]
    facts = sec.extract_annual_facts(cf, fy_ends, as_of_filed=report.filing_date)
    db.query(FinancialFact).filter_by(deal_id=deal.id, kind="reported").delete()
    for f in facts:
        db.add(FinancialFact(deal_id=deal.id, metric=f["metric"], fiscal_year=f["fiscal_year"], value=f["value"],
                             unit=f["unit"], currency=f["currency"], kind="reported", status=f["status"],
                             status_reason=f.get("status_reason"), xbrl_tag=f.get("xbrl_tag"),
                             accession=f.get("accession"), form=f.get("form"), filed=f.get("filed"),
                             period_start=f.get("period_start"), period_end=f["period_end"],
                             source_record_id=rec_cf.id, restated=f.get("restated", False),
                             restatement_note=f.get("restatement_note"), revision_note=f.get("revision_note")))
        if f["status"] == "ok":
            build.facts_written += 1
        else:
            build.facts_missing.append(f"{f['metric']} FY{f['fiscal_year']}")
        if f.get("restated"):
            build.restated.append(f"{f['metric']} FY{f['fiscal_year']}: {f['restatement_note']}")
    db.flush()
    _reconcile_with_filings(db, deal, subs, company.id, mode, build)
    materialize_calculations(db, deal)
    debt = db.query(FinancialFact).filter_by(deal_id=deal.id, metric="total_debt",
                                             fiscal_year=report.report_date.year).first()
    if deal_type == "credit" and debt and debt.value is not None:
        deal.deal_size_musd = round(debt.value, 1)
        deal.deal_size_basis = (f"Credit exposure reference: total debt ({debt.xbrl_tag}, book value) at "
                                f"{report.report_date.isoformat()} per Form 10-K {report.accession}")
    else:
        deal.deal_size_musd, deal.deal_size_basis = None, "No transaction value: not applicable or not disclosed"

    # ---- the 10-K itself, split into Items, stored verbatim (normalised) with offsets
    doc_r = sec.get_filing_document(report, mode)
    amend_note = ("; amendments on file: " + ", ".join(f"10-K/A {a['accession']} filed {a['filing_date']}"
                                                     for a in report.amendments)) if report.amendments else ""
    rec_doc = _record(db, doc_r, company_id=company.id, accession=report.accession, form=report.form,
                      filing_date=report.filing_date, period_end=report.report_date,
                      notes="Form 10-K primary document (original filing used)" + amend_note)
    full = html_to_text(doc_r.text())
    for sec_ in split_items(full):
        if sec_.doc_type not in KEEP_TYPES or len(sec_.text) < 200:
            continue
        sha = hashlib.sha256(sec_.text.encode()).hexdigest()
        if db.query(Document).filter_by(deal_id=deal.id, sha256=sha).first():
            build.documents_unchanged += 1
            continue
        filename = f"10-K FY{report.report_date.year} Item {sec_.item} - {sec_.title}.txt"
        doc_id = uuid.uuid4().hex
        res = ingest_text(deal.id, doc_id, filename, sec_.text, doc_type=sec_.doc_type)
        db.add(Document(id=doc_id, deal_id=deal.id, filename=filename, doc_type=sec_.doc_type,
                        title=f"Form 10-K Item {sec_.item}: {sec_.title}", sha256=res.sha256, n_chars=res.n_chars,
                        n_chunks=res.n_chunks, pii_redactions=res.redactions, injection_flags=len(res.injection_hits),
                        data_classification="verified_real", source_record_id=rec_doc.id, source_url=report.url,
                        accession=report.accession, period_end=report.report_date, section_offset=sec_.start,
                        uploaded_by=owner_id))
        build.documents_added += 1

    # ---- FRED macro context
    for sid in MACRO_SERIES:
        try:
            obs, fr = fred.get_series(sid, mode)
            rec = _record(db, fr, notes=f"FRED {sid}: {fred.SERIES.get(sid, '')}")
            lo, hi = date(report.report_date.year - 1, 1, 1), report.report_date
            for d, v in obs:
                if lo <= d <= hi and not db.query(MacroObservation).filter_by(series_id=sid, obs_date=d).first():
                    db.add(MacroObservation(series_id=sid, obs_date=d, value=v, source_record_id=rec.id))
            out_sources.append({"source": f"FRED {sid}", "url": fr.url, "retrieved_at": fr.retrieved_at.isoformat(),
                                "mode": fr.mode})
        except SourceUnavailable as exc:
            build.warnings.append(f"FRED {sid} unavailable: {exc}")

    for r in (subs_r, cf_r, doc_r):
        out_sources.append({"source": r.source, "url": r.url, "retrieved_at": r.retrieved_at.isoformat(), "mode": r.mode})
    build.sources = out_sources
    if report.amendments:
        build.warnings.append(f"10-K/A amendments exist for this period: {report.amendments}")
    db.flush()
    return build
