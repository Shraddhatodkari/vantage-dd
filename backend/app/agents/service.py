"""Run orchestration: versioned analysis runs, persisted progress, partner review, immutable reports.

* Each run gets a per-deal version number and an `inputs_hash` (documents + financial facts + methodology),
  so a report can always be traced to the exact inputs it was produced from.
* A run whose agents failed is marked `incomplete` and can never be approved.
* On approval the memo is rendered from the persisted findings and stored as an immutable ReportVersion.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import Counter
from datetime import date, datetime, timezone

from langgraph.types import Command
from sqlalchemy import update as sql_update
from sqlalchemy.orm import Session

from app.agents.graph import get_graph
from app.agents.prompts import PROMPT_VERSION
from app.agents.quality import METHODOLOGY_VERSION
from app.agents.report import build_report
from app.analytics.metrics import METHODOLOGY_VERSION as METRICS_VERSION
from app.analytics.strengths import strengths
from app.core.config import get_settings
from app.db.models import (
    AnalysisRun,
    Company,
    Deal,
    Document,
    FinancialFact,
    Finding,
    ReportVersion,
    RunEvent,
    SourceRecord,
    User,
)
from app.db.session import SessionLocal
from app.mlops.tracking import log_agent_run

log = logging.getLogger("vantage.service")
METHODOLOGY = f"{METHODOLOGY_VERSION}/{METRICS_VERSION}"
_run_lock = threading.Lock()


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def inputs_hash(db: Session, deal_id: str) -> str:
    docs = sorted(d.sha256 for d in db.query(Document).filter_by(deal_id=deal_id))
    facts = sorted((f.metric, f.fiscal_year, f.kind, f.value, f.accession) for f in
                   db.query(FinancialFact).filter_by(deal_id=deal_id))
    return hashlib.sha256(_canon({"docs": docs, "facts": facts, "method": METHODOLOGY}).encode()).hexdigest()


def findings_hash(findings: list[dict]) -> str:
    keys = ("code", "title", "detail", "severity", "claim_type", "verification_status", "evidence")
    rows = sorted((_canon({k: f.get(k) for k in keys}) for f in findings))
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()


def create_run(db: Session, deal: Deal, question: str, user_id: str) -> AnalysisRun:
    with _run_lock:  # one active run per deal; version numbers are unique per deal (DB constraint too)
        active = db.query(AnalysisRun).filter(AnalysisRun.deal_id == deal.id,
                                              AnalysisRun.status.in_(["queued", "running"])).first()
        if active:
            raise RuntimeError("An analysis is already running for this deal")
        version = (max((r.version for r in deal.runs), default=0)) + 1
        run = AnalysisRun(deal_id=deal.id, version=version, question=question, started_by=user_id,
                          methodology_version=METHODOLOGY, inputs_hash=inputs_hash(db, deal.id),
                          as_of_date=date.today())
        db.add(run)
        deal.status = "analysing"
        db.commit()
        return run


def _persist_events(db: Session, run_id: str, events: list[dict]) -> None:
    seq = db.query(RunEvent).filter_by(run_id=run_id).count()
    for e in events:
        seq += 1
        db.add(RunEvent(run_id=run_id, seq=seq, agent=e["agent"], status=e.get("status", "ok"),
                        message=e["message"], latency_ms=e.get("latency_ms", 0)))
    db.commit()


def _config(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


def execute_run(run_id: str) -> None:
    db = SessionLocal()
    t0 = time.perf_counter()
    try:
        run = db.get(AnalysisRun, run_id)
        deal = db.get(Deal, run.deal_id)
        run.status = "running"
        db.commit()
        state = {"run_id": run_id, "question": run.question,
                 "deal": {"id": deal.id, "name": deal.name, "target_company": deal.target_company,
                          "deal_type": deal.deal_type, "sector": deal.sector}}
        graph = get_graph()
        for update in graph.stream(state, _config(run_id), stream_mode="updates"):
            for _node, delta in update.items():
                if isinstance(delta, dict) and delta.get("events"):
                    _persist_events(db, run_id, delta["events"])
        final = graph.get_state(_config(run_id)).values
        validated, rejected = final.get("validated_findings", []), final.get("rejected_findings", [])
        for f in validated + rejected:
            db.add(Finding(run_id=run_id, code=f["code"], agent=f["agent"], category=f["category"],
                           severity=f["severity"], claim_type=f["claim_type"], title=f["title"], detail=f["detail"],
                           evidence=f["evidence"], limitations=f.get("limitations"),
                           verification_status=f["verification_status"],
                           verification_notes=f.get("verification_notes", [])))
        errors = final.get("agent_errors", [])
        sev = Counter(f["severity"] for f in validated)
        latency = Counter()
        for e in final.get("events", []):
            latency[e["agent"]] += e.get("latency_ms", 0)
        metrics = {"n_candidates": len(final.get("findings", [])), "n_accepted": len(validated),
                   "n_verified": sum(f["verification_status"] == "verified" for f in validated),
                   "n_supported": sum(f["verification_status"] == "supported" for f in validated),
                   "n_rejected": len(rejected), **{f"n_{k}": sev.get(k, 0) for k in ("critical", "high", "medium", "low")},
                   "total_latency_ms": int((time.perf_counter() - t0) * 1000),
                   **{f"latency_ms_{k}": v for k, v in latency.items()},
                   "risk_breakdown": final.get("risk_breakdown", {})}
        run.metrics = metrics
        run.agent_errors = [{k: e[k] for k in ("agent", "error")} for e in errors]
        run.coverage = final.get("coverage", [])
        metrics["llm_status"] = sorted({c.get("llm", "not_configured") for c in run.coverage})
        run.risk_score = final.get("risk_score")
        run.recommendation = final.get("recommendation")
        if final.get("incomplete"):
            run.status = "incomplete"
            deal.status = "open"
        else:
            run.status = "completed"          # draft: the analyst reviews it and submits it for partner review
            deal.status = "analysed"
            deal.risk_score, deal.risk_score_run_id = run.risk_score, run.id
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        s = get_settings()
        log_agent_run(run_id, {"llm_provider": s.llm_provider, "llm_model": s.llm_model, "prompt_version": PROMPT_VERSION,
                               "methodology": METHODOLOGY, "deal_type": deal.deal_type,
                               "classification": deal.data_classification},
                      {k: v for k, v in metrics.items() if isinstance(v, (int, float))} | (
                          {"risk_score": run.risk_score} if run.risk_score is not None else {}),
                      tags={"deal": deal.name})
    except Exception as exc:  # noqa: BLE001
        log.exception("run failed")
        db.rollback()
        run = db.get(AnalysisRun, run_id)
        run.status = "failed"
        run.agent_errors = [{"agent": "orchestrator", "error": f"{type(exc).__name__}: {str(exc)[:400]}"}]
        run.finished_at = datetime.now(timezone.utc)
        db.get(Deal, run.deal_id).status = "open"
        db.commit()
    finally:
        db.close()


def start_run_async(run_id: str) -> threading.Thread:
    t = threading.Thread(target=execute_run, args=(run_id,), daemon=True, name=f"run-{run_id[:8]}")
    t.start()
    return t


def recover_interrupted_runs() -> int:
    """Runs left queued/running by a crash or restart are marked failed (never shown as complete)."""
    with SessionLocal() as db:
        stuck = db.query(AnalysisRun).filter(AnalysisRun.status.in_(["queued", "running"])).all()
        for r in stuck:
            r.status = "failed"
            r.agent_errors = (r.agent_errors or []) + [{"agent": "orchestrator",
                                                        "error": "interrupted by an API restart; start a new run"}]
            r.finished_at = datetime.now(timezone.utc)
            deal = db.get(Deal, r.deal_id)
            if deal.status == "analysing":
                deal.status = "open"
        # a review claim interrupted by a crash (no report written) goes back to the review queue
        released = db.execute(sql_update(AnalysisRun).where(AnalysisRun.status == "reviewing").values(status="awaiting_review"))
        db.commit()
        return len(stuck) + (released.rowcount or 0)


def finding_dicts(run: AnalysisRun, status: str | None = None) -> list[dict]:
    rows = [f for f in run.findings if status is None or (f.verification_status == "rejected") == (status == "rejected")]
    return [{"id": f.id, "code": f.code, "agent": f.agent, "category": f.category, "severity": f.severity,
             "claim_type": f.claim_type, "title": f.title, "detail": f.detail, "evidence": f.evidence,
             "limitations": f.limitations, "verification_status": f.verification_status,
             "verification_notes": f.verification_notes} for f in rows]


def _email(db: Session, user_id: str | None) -> str | None:
    u = db.get(User, user_id) if user_id else None
    return u.email if u else None


def _mode_text(sources: list[dict]) -> str:
    modes = {s["mode"] for s in sources}
    if not modes:
        return "uploaded or illustrative files (no external sources)"
    if modes == {"snapshot"}:
        return "stored snapshots of SEC/GLEIF/FRED retrievals (not re-checked live during this run)"
    return "live retrieval" if modes == {"live"} else "mix of live retrievals and stored snapshots"


def report_inputs(db: Session, run: AnalysisRun, approval: dict) -> dict:
    deal = db.get(Deal, run.deal_id)
    comp = db.get(Company, deal.company_id) if deal.company_id else None
    fin = [{"metric": f.metric, "fiscal_year": f.fiscal_year, "value": f.value, "unit": f.unit, "kind": f.kind,
            "status": f.status, "status_reason": f.status_reason, "xbrl_tag": f.xbrl_tag, "formula": f.formula,
            "source_document": f.source_document, "document_check": f.document_check,
            "revision_note": f.revision_note} for f in db.query(FinancialFact).filter_by(deal_id=deal.id)]
    sources = []
    if comp:
        seen = set()
        q = db.query(SourceRecord).filter((SourceRecord.company_id == comp.id) | (SourceRecord.source == "fred"))
        for r in q.order_by(SourceRecord.retrieved_at):
            if r.url not in seen:
                seen.add(r.url)
                sources.append({"source": r.source, "url": r.url,
                                "retrieved_at": r.retrieved_at.replace(microsecond=0, tzinfo=None).isoformat(sep=" "),
                                "mode": r.retrieval_mode, "accession": r.accession,
                                "filing_date": r.filing_date.isoformat() if r.filing_date else None})
    return {"deal": {"name": deal.name, "target_company": deal.target_company, "deal_type": deal.deal_type,
                     "sector": deal.sector, "data_classification": deal.data_classification,
                     "is_historical": deal.is_historical, "currency": deal.currency,
                     "reporting_period_end": deal.reporting_period_end.isoformat() if deal.reporting_period_end else None},
            "company": {"cik": comp.cik, "tickers": comp.tickers, "lei": comp.lei, "lei_status": comp.lei_status,
                        "lei_match": comp.lei_match} if comp else None,
            "run": {"id": run.id, "version": run.version,
                    "created_at": run.created_at.replace(microsecond=0, tzinfo=None).isoformat(sep=" "),
                    "inputs_hash": run.inputs_hash, "methodology_version": run.methodology_version,
                    "risk_score": run.risk_score, "recommendation": run.recommendation},
            "coverage": run.coverage or [],
            "strengths": strengths({(f["metric"], f["fiscal_year"]): f for f in fin},
                                   deal.reporting_period_end.year if deal.reporting_period_end else
                                   max((f["fiscal_year"] for f in fin if f["kind"] == "reported"), default=None)),
            "history": {"started_by": _email(db, run.started_by), "submitted_by": _email(db, run.submitted_by),
                        "submitted_at": run.submitted_at.replace(microsecond=0, tzinfo=None).isoformat(sep=" ")
                        if run.submitted_at else None,
                        "submission_note": run.submission_note},
            "source_mode_text": _mode_text(sources),
            "historical_cutoff": deal.historical_cutoff.isoformat() if deal.historical_cutoff else None,
            "breakdown": (run.metrics or {}).get("risk_breakdown", {}), "validated": finding_dicts(run, "accepted"),
            "rejected": finding_dicts(run, "rejected"), "financials": fin, "sources": sources, "approval": approval}


class ReviewError(ValueError):
    pass


def submit_run(run_id: str, note: str | None, user_id: str) -> AnalysisRun:
    """Analyst submits a completed run for partner review. Atomic: a run can be submitted once."""
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        if run.status != "completed":
            raise ReviewError(f"Run is '{run.status}'; only a completed run can be submitted for review")
        newer = db.query(AnalysisRun).filter(AnalysisRun.deal_id == run.deal_id, AnalysisRun.version > run.version).count()
        if newer:
            raise ReviewError(f"Analysis v{run.version} is superseded by a newer version; submit the latest version")
        deal = db.get(Deal, run.deal_id)
        if run.inputs_hash != inputs_hash(db, deal.id):
            raise ReviewError("The deal's documents or financial data changed after this run; start a new run")
        res = db.execute(sql_update(AnalysisRun).where(AnalysisRun.id == run_id, AnalysisRun.status == "completed")
                         .values(status="awaiting_review", submitted_by=user_id, submitted_at=datetime.now(timezone.utc),
                                 submission_note=note))
        if res.rowcount != 1:
            db.rollback()
            raise ReviewError("This run was already submitted")
        deal.status = "in_review"
        _persist_events(db, run_id, [{"agent": "analyst_submission",
                                      "message": "Analysis submitted for partner review."}])
        db.commit()
        db.refresh(run)
        return run
    finally:
        db.close()


def review_run(run_id: str, decision: str, note: str | None, reviewer_email: str, reviewer_id: str) -> AnalysisRun:
    if decision == "rejected" and len((note or "").strip()) < 10:
        raise ReviewError("A rejection must state the reason")
    db = SessionLocal()
    claimed = False
    try:
        run = db.get(AnalysisRun, run_id)
        if run.status != "awaiting_review":
            raise ReviewError(f"Run is '{run.status}', not awaiting review")
        if reviewer_id in (run.started_by, run.submitted_by):
            raise ReviewError("Segregation of duties: the person who started or submitted a run cannot review it")
        deal = db.get(Deal, run.deal_id)
        if run.inputs_hash != inputs_hash(db, deal.id):
            raise ReviewError("The deal's documents or financial data changed after this run; start a new run")
        # Atomic claim (compare-and-set): exactly one concurrent reviewer can move the run out of awaiting_review.
        res = db.execute(sql_update(AnalysisRun).where(AnalysisRun.id == run_id, AnalysisRun.status == "awaiting_review")
                         .values(status="reviewing"))
        db.commit()
        if res.rowcount != 1:
            raise ReviewError("This run was already reviewed by someone else")
        claimed = True
        db.refresh(run)
        now = datetime.now(timezone.utc)
        graph = get_graph()
        snap = graph.get_state(_config(run_id))
        if snap and snap.next:  # close the paused graph thread (state is persisted in SQLite)
            for update in graph.stream(Command(resume={"decision": decision, "note": note, "reviewer": reviewer_email}),
                                       _config(run_id), stream_mode="updates"):
                for _n, delta in update.items():
                    if isinstance(delta, dict) and delta.get("events"):
                        _persist_events(db, run_id, delta["events"])
        else:
            _persist_events(db, run_id, [{"agent": "human_review", "message": f"Partner decision: {decision} by {reviewer_email}."}])
        run.reviewer_id, run.review_note, run.reviewed_at = reviewer_id, note, now
        if decision == "approved":
            fh = findings_hash(finding_dicts(run, "accepted"))
            approval = {"by": reviewer_email, "at": now.replace(microsecond=0, tzinfo=None).isoformat(sep=" "), "note": note,
                        "report_version": 1, "findings_sha256": fh}
            md = build_report(report_inputs(db, run, approval))
            db.add(ReportVersion(run_id=run.id, version=1, content_md=md,
                                 content_sha256=hashlib.sha256(md.encode()).hexdigest(), findings_sha256=fh,
                                 inputs_hash=run.inputs_hash, methodology_version=run.methodology_version,
                                 approved_by=reviewer_email, approved_at=now))
            _persist_events(db, run_id, [{"agent": "report_writer",
                                          "message": "Investment committee memo v1 generated from the approved findings."}])
            run.status, deal.status = "approved", "approved"
        else:
            run.status, deal.status = "rejected", "rework"
        db.commit()
        claimed = False
        db.refresh(run)
        return run
    except Exception:
        db.rollback()
        if claimed:   # release the claim so the review can be retried
            db.execute(sql_update(AnalysisRun).where(AnalysisRun.id == run_id, AnalysisRun.status == "reviewing")
                       .values(status="awaiting_review"))
            db.commit()
        raise
    finally:
        db.close()
