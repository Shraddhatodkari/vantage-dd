from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserOut(ORM):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    is_demo_account: bool = False
    totp_enabled: bool = False
    failed_logins: int = 0
    last_login_at: datetime | None = None


class SessionOut(BaseModel):
    user: UserOut
    permissions: list[str]
    access_expires_at: datetime
    mfa_setup_required: bool = False      # the role requires 2FA and the user has not enrolled yet


class MfaChallenge(BaseModel):
    mfa_required: bool = True             # password accepted; submit the authenticator code to /auth/login/mfa


class CodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class MfaDisableIn(BaseModel):
    password: str = Field(min_length=1, max_length=256)
    code: str = Field(min_length=6, max_length=8)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)
    code: str | None = Field(default=None, max_length=8)   # required when 2FA is enabled


class PasswordResetIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=1, max_length=256)


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=12, max_length=256)
    role: Literal["analyst", "partner", "admin"] = "analyst"


class PublicConfig(BaseModel):
    app_name: str
    env: str
    demo_mode: bool
    demo_accounts: list[dict]   # emails + roles only; never passwords
    source_mode: str


class DealCreate(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    target_company: str = Field(min_length=2, max_length=255)
    deal_type: Literal["m_and_a", "credit", "vendor_risk"]
    sector: str = Field(min_length=2, max_length=80)
    deal_size_musd: float | None = Field(default=None, ge=0, le=10_000_000)
    deal_size_basis: str | None = Field(default=None, max_length=300)


class DocumentOut(ORM):
    id: str
    filename: str
    doc_type: str
    title: str | None
    n_chars: int
    n_chunks: int
    pii_redactions: int
    injection_flags: int
    data_classification: str
    source_url: str | None
    accession: str | None
    period_end: date | None
    uploaded_at: datetime


class CompanyOut(ORM):
    name: str
    cik: str | None
    tickers: list
    sic: str | None
    sic_description: str | None
    state_of_incorporation: str | None
    lei: str | None
    lei_legal_name: str | None
    lei_status: str | None
    lei_match: str | None
    lei_record: dict = {}


class DealOut(ORM):
    id: str
    name: str
    target_company: str
    deal_type: str
    sector: str
    data_classification: str
    is_historical: bool
    reporting_period_end: date | None
    historical_cutoff: date | None = None
    currency: str
    deal_size_musd: float | None
    deal_size_basis: str | None
    status: str
    risk_score: float | None
    risk_score_run_id: str | None
    created_at: datetime
    # version state, derived from the run records (not from the stored deal.status, which records the last action)
    latest_version: int | None = None
    latest_status: str | None = None
    approved_version: int | None = None
    approved_risk_score: float | None = None
    approved_run_id: str | None = None


class DealMetaOut(ORM):
    """What an admin without deal membership may see: no evidence, findings or reports."""
    id: str
    name: str
    data_classification: str
    status: str
    created_at: datetime


class SourceOut(BaseModel):
    source: str
    label: str = ""
    notes: str | None = None
    url: str
    retrieved_at: datetime
    retrieval_mode: str
    accession: str | None
    filing_date: date | None
    age_days: int
    stale: bool
    # time basis relative to the deal's historical cut-off, and whether the source feeds the risk score
    time_basis: str = "unknown"          # historical | point_in_time_filtered | current_metadata
    used_in_scoring: bool = False
    basis_note: str | None = None


class DealDetail(DealOut):
    documents: list[DocumentOut]
    company: CompanyOut | None
    sources: list[SourceOut] = []
    members: list[dict] = []


class FactOut(ORM):
    id: str
    metric: str
    fiscal_year: int
    period_start: date | None
    period_end: date | None
    value: float | None
    unit: str
    currency: str | None
    kind: str
    status: str
    status_reason: str | None
    xbrl_tag: str | None
    accession: str | None
    form: str | None
    filed: date | None
    source_document: str | None
    formula: str | None
    inputs: list
    restated: bool
    restatement_note: str | None
    document_check: str = "not_checked"
    document_check_detail: str | None = None
    revision_note: str | None = None
    document_passage: str | None = None
    filing_url: str | None = None


class RunCreate(BaseModel):
    question: str = Field(default="Full due diligence: identify deal-breakers, valuation risks and required protections.",
                          max_length=2000)


class FindingOut(ORM):
    id: str
    code: str
    agent: str
    category: str
    severity: str
    claim_type: str
    title: str
    detail: str
    evidence: list[dict]
    limitations: str | None
    verification_status: str
    verification_notes: list
    created_at: datetime
    score_weight: float | None = None     # severity weight × verification factor (0 for rejected)
    score_points: float | None = None     # this finding's share of the run's risk score


class EventOut(ORM):
    seq: int
    agent: str
    status: str
    message: str
    latency_ms: int
    created_at: datetime


class ReportMeta(ORM):
    id: str
    version: int
    content_sha256: str
    findings_sha256: str
    inputs_hash: str | None
    methodology_version: str
    approved_by: str
    approved_at: datetime


class RunOut(ORM):
    id: str
    deal_id: str
    version: int
    status: str
    question: str
    methodology_version: str
    inputs_hash: str | None
    as_of_date: date | None
    risk_score: float | None
    recommendation: str | None
    metrics: dict
    agent_errors: list
    coverage: list = []
    started_by: str
    submitted_by: str | None = None
    submitted_at: datetime | None = None
    submission_note: str | None = None
    reviewer_id: str | None
    review_note: str | None
    reviewed_at: datetime | None
    created_at: datetime
    finished_at: datetime | None


class RunDetail(RunOut):
    findings: list[FindingOut]
    events: list[EventOut]
    reports: list[ReportMeta]
    inputs_changed_since_run: bool = False


class ReportOut(ReportMeta):
    content_md: str


class SubmitIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class ReviewIn(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _rejection_needs_reason(self):
        if self.decision == "rejected" and len((self.note or "").strip()) < 10:
            raise ValueError("A rejection must state the reason (at least 10 characters) so the analyst can act on it")
        return self


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class AskOut(BaseModel):
    answer: str
    # llm_grounded: AI answer that passed citation/number validation; abstained: the sources do not answer it;
    # extractive: passages only (offline mode, provider failure or an AI answer that failed validation)
    answer_type: Literal["extractive", "llm_grounded", "abstained"]
    citations: list[dict]
    withheld_reason: str | None = None


class MemberIn(BaseModel):
    user_id: str


class AuditOut(ORM):
    id: int
    user_email: str | None
    action: str
    resource: str
    outcome: str
    detail: dict
    ip: str | None
    created_at: datetime
    hash: str


class PortfolioGroup(BaseModel):
    deals: int
    deals_scored: int
    avg_risk: float | None
    awaiting_review: int
    findings_by_severity: dict[str, int]
    findings_by_category: dict[str, int]
    findings_accepted: int
    findings_rejected: int
    exposure_musd: float | None
    exposure_note: str
    ready_to_submit: int = 0
    approved: int = 0
    deals_with_gaps: int = 0          # deals whose latest scored run has an evidence category with insufficient evidence
    gap_categories: int = 0
    reported_facts: int = 0
    facts_confirmed_in_filing: int = 0
    facts_composite: int = 0        # sum of several separately printed lines (the total itself is not printed)
    sources: dict = {}                # {"count", "modes", "oldest_retrieval_days", "stale"}
    deals_detail: list[dict] = []     # per deal: name, score, recommendation, run status, gaps, severities


class ActivityOut(BaseModel):
    at: datetime
    deal_id: str
    deal: str
    action: str
    by: str | None
    version: int
    detail: str | None = None


class PortfolioStats(BaseModel):
    verified_real: PortfolioGroup
    illustrative: PortfolioGroup
    user_supplied: PortfolioGroup
    definitions: dict[str, str]
