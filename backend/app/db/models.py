"""Relational model (SQLite for local/Windows use, Postgres supported). Schema changes go through
Alembic migrations in backend/migrations."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- identity & access
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="analyst")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo_account: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # two-factor authentication: secret encrypted at rest; last accepted time step blocks code replay
    totp_secret_enc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_last_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # sessions issued before this moment are rejected (password change / reset signs out everywhere)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PasswordResetToken(Base):
    """Administrator-issued, single-use, time-limited reset link. Only the SHA-256 of the token is stored."""
    __tablename__ = "password_reset_tokens"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# --------------------------------------------------------------------------- companies & sources
class Company(Base):
    """A real legal entity, identified by SEC CIK and (where found) GLEIF LEI."""
    __tablename__ = "companies"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    cik: Mapped[str | None] = mapped_column(String(10), unique=True, nullable=True)
    tickers: Mapped[list] = mapped_column(JSON, default=list)
    sic: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sic_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fiscal_year_end: Mapped[str | None] = mapped_column(String(4), nullable=True)  # MMDD
    state_of_incorporation: Mapped[str | None] = mapped_column(String(10), nullable=True)
    lei: Mapped[str | None] = mapped_column(String(20), nullable=True)
    lei_legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lei_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    lei_match: Mapped[str | None] = mapped_column(String(40), nullable=True)  # exact | ambiguous | not_found
    lei_record: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SourceRecord(Base):
    """One retrieval of one external resource. Raw bytes are kept on disk (sha256-addressed)."""
    __tablename__ = "source_records"
    __table_args__ = (UniqueConstraint("url", "sha256", name="uq_source_url_sha"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    source: Mapped[str] = mapped_column(String(40))  # sec_submissions | sec_companyfacts | sec_filing | gleif | fred
    url: Mapped[str] = mapped_column(String(1000))
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    accession: Mapped[str | None] = mapped_column(String(25), nullable=True)
    form: Mapped[str | None] = mapped_column(String(20), nullable=True)
    filing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retrieval_mode: Mapped[str] = mapped_column(String(20))  # live | snapshot
    sha256: Mapped[str] = mapped_column(String(64))
    bytes: Mapped[int] = mapped_column(Integer)
    local_path: Mapped[str] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class FinancialFact(Base):
    """A single number: either reported by a source (kind=reported) or deterministically
    calculated from reported facts (kind=calculated, with formula + input fact ids)."""
    __tablename__ = "financial_facts"
    __table_args__ = (UniqueConstraint("deal_id", "metric", "fiscal_year", name="uq_fact_deal_metric_year"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    deal_id: Mapped[str] = mapped_column(ForeignKey("deals.id"), index=True)
    metric: Mapped[str] = mapped_column(String(60))
    fiscal_year: Mapped[int] = mapped_column(Integer)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)  # None = not available / not meaningful
    unit: Mapped[str] = mapped_column(String(20))  # USD_millions | pct | x | days
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    kind: Mapped[str] = mapped_column(String(12))  # reported | calculated
    status: Mapped[str] = mapped_column(String(20), default="ok")  # ok | missing | not_meaningful
    status_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    xbrl_tag: Mapped[str | None] = mapped_column(String(120), nullable=True)
    accession: Mapped[str | None] = mapped_column(String(25), nullable=True)
    form: Mapped[str | None] = mapped_column(String(20), nullable=True)
    filed: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_record_id: Mapped[str | None] = mapped_column(ForeignKey("source_records.id"), nullable=True)
    source_document: Mapped[str | None] = mapped_column(String(255), nullable=True)
    formula: Mapped[str | None] = mapped_column(String(300), nullable=True)
    inputs: Mapped[list] = mapped_column(JSON, default=list)
    restated: Mapped[bool] = mapped_column(Boolean, default=False)
    restatement_note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Independent check of the XBRL value against the text of the filing it came from:
    # matched | not_found | not_checked | not_applicable
    document_check: Mapped[str] = mapped_column(String(20), default="not_checked")
    document_check_detail: Mapped[str | None] = mapped_column(String(400), nullable=True)
    revision_note: Mapped[str | None] = mapped_column(String(600), nullable=True)   # revised before the cut-off
    document_passage: Mapped[str | None] = mapped_column(String(400), nullable=True)  # filing text with the value


class MacroObservation(Base):
    __tablename__ = "macro_observations"
    __table_args__ = (UniqueConstraint("series_id", "obs_date", name="uq_macro_series_date"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id: Mapped[str] = mapped_column(String(40), index=True)
    obs_date: Mapped[date] = mapped_column(Date)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_record_id: Mapped[str] = mapped_column(ForeignKey("source_records.id"))


# --------------------------------------------------------------------------- deals
class Deal(Base):
    __tablename__ = "deals"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    target_company: Mapped[str] = mapped_column(String(255))
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    deal_type: Mapped[str] = mapped_column(String(40))  # m_and_a | credit | vendor_risk
    sector: Mapped[str] = mapped_column(String(80))
    # verified_real: built only from retrieved authoritative sources; illustrative: synthetic fixture;
    # user_supplied: uploaded by users, not independently verified.
    data_classification: Mapped[str] = mapped_column(String(20), default="user_supplied")
    is_historical: Mapped[bool] = mapped_column(Boolean, default=False)
    reporting_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Historical cut-off: no information filed/published after this date may influence the analysis.
    historical_cutoff: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    deal_size_musd: Mapped[float | None] = mapped_column(Float, nullable=True)
    deal_size_basis: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="open")
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    documents: Mapped[list[Document]] = relationship(back_populates="deal", cascade="all, delete-orphan")
    runs: Mapped[list[AnalysisRun]] = relationship(back_populates="deal", cascade="all, delete-orphan")
    company: Mapped[Company | None] = relationship()


class DealMember(Base):
    __tablename__ = "deal_members"
    __table_args__ = (UniqueConstraint("deal_id", "user_id", name="uq_deal_member"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deal_id: Mapped[str] = mapped_column(ForeignKey("deals.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    added_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("deal_id", "sha256", name="uq_doc_deal_sha"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    deal_id: Mapped[str] = mapped_column(ForeignKey("deals.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    doc_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64))
    n_chars: Mapped[int] = mapped_column(Integer, default=0)
    n_chunks: Mapped[int] = mapped_column(Integer, default=0)
    pii_redactions: Mapped[int] = mapped_column(Integer, default=0)
    injection_flags: Mapped[int] = mapped_column(Integer, default=0)
    data_classification: Mapped[str] = mapped_column(String(20), default="user_supplied")
    source_record_id: Mapped[str | None] = mapped_column(ForeignKey("source_records.id"), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    accession: Mapped[str | None] = mapped_column(String(25), nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    section_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)  # start in the full filing text
    uploaded_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    deal: Mapped[Deal] = relationship(back_populates="documents")


# --------------------------------------------------------------------------- analysis
class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (UniqueConstraint("deal_id", "version", name="uq_run_deal_version"),
                      Index("ix_runs_deal_status", "deal_id", "status"))          # index created by migration 0002
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    deal_id: Mapped[str] = mapped_column(ForeignKey("deals.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    # queued -> running -> completed (draft) | incomplete | failed ; completed -> awaiting_review (analyst submits)
    # -> reviewing (partner claim) -> approved | rejected
    question: Mapped[str] = mapped_column(Text, default="")
    methodology_version: Mapped[str] = mapped_column(String(20), default="")
    inputs_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # docs + facts snapshot
    as_of_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(String(60), nullable=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    agent_errors: Mapped[list] = mapped_column(JSON, default=list)
    # What each specialist actually reviewed (documents, facts, rules, LLM status) — coverage disclosure
    coverage: Mapped[list] = mapped_column(JSON, default=list)
    started_by: Mapped[str] = mapped_column(String(32))
    submitted_by: Mapped[str | None] = mapped_column(String(32), nullable=True)      # analyst who submitted
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submission_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    deal: Mapped[Deal] = relationship(back_populates="runs")
    findings: Mapped[list[Finding]] = relationship(back_populates="run", cascade="all, delete-orphan")
    events: Mapped[list[RunEvent]] = relationship(back_populates="run", cascade="all, delete-orphan",
                                                  order_by="RunEvent.seq")
    reports: Mapped[list[ReportVersion]] = relationship(back_populates="run", order_by="ReportVersion.version")


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (Index("ix_findings_run_code", "run_id", "code"),)    # created by migration 0002
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    code: Mapped[str] = mapped_column(String(60))
    agent: Mapped[str] = mapped_column(String(40))
    category: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(10))
    claim_type: Mapped[str] = mapped_column(String(20))  # source_fact | calculation | interpretation | assumption
    title: Mapped[str] = mapped_column(String(300))
    detail: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(20))  # verified | supported | rejected
    verification_notes: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    run: Mapped[AnalysisRun] = relationship(back_populates="findings")


class RunEvent(Base):
    __tablename__ = "run_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    agent: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(10), default="ok")  # ok | error
    message: Mapped[str] = mapped_column(Text)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    run: Mapped[AnalysisRun] = relationship(back_populates="events")


class ReportVersion(Base):
    """Immutable approved IC memo. Exports serve exactly this content; sha256 lets anyone check it."""
    __tablename__ = "report_versions"
    __table_args__ = (UniqueConstraint("run_id", "version", name="uq_report_run_version"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_runs.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    content_md: Mapped[str] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64))
    findings_sha256: Mapped[str] = mapped_column(String(64))
    inputs_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    methodology_version: Mapped[str] = mapped_column(String(20))
    approved_by: Mapped[str] = mapped_column(String(255))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    run: Mapped[AnalysisRun] = relationship(back_populates="reports")


# --------------------------------------------------------------------------- audit
class AuditLog(Base):
    """Append-only, hash-chained. UPDATE/DELETE are blocked by database triggers (see migrations) and
    by ORM guards; `GET /admin/audit/verify` recomputes the chain."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    resource: Mapped[str] = mapped_column(String(120))
    outcome: Mapped[str] = mapped_column(String(20), default="success")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
