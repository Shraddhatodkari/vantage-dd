"""Vantage DD — Model Context Protocol (MCP) server.

Exposes the platform's audited tools to MCP clients (Claude Desktop, Claude Code, IDE agents).
The server acts on behalf of ONE configured user (VANTAGE_MCP_USER_EMAIL) and applies the same
deal-membership and permission rules as the web API; every tool call is written to the audit log.
It is intended for local (stdio) use on the analyst's own machine.

Run:  python -m mcp_server.server          (from the backend folder)
"""
from __future__ import annotations

import os

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

from app.analytics.metrics import fmt  # noqa: E402
from app.core.permissions import Perm, has_perm  # noqa: E402
from app.db.audit import write_audit  # noqa: E402
from app.db.models import Deal, DealMember, FinancialFact, User  # noqa: E402
from app.db.seed import init_db  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.guardrails.input_guards import guard_question, redact_pii  # noqa: E402
from app.rag.retriever import HybridRetriever  # noqa: E402
from app.tools.clauses import scan_clauses  # noqa: E402
from app.tools.finance import covenant_test  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402

server = MCPServer("vantage-dd", instructions=(
    "Due-diligence tools. Call list_deals first. Financial values come with their source (XBRL tag + "
    "accession, or uploaded file) and calculations with their formula; cite them."))


def _user(db) -> User:
    email = os.getenv("VANTAGE_MCP_USER_EMAIL")
    u = db.query(User).filter_by(email=(email or "").lower(), is_active=True).first() if email else None
    if not u:
        raise PermissionError("Set VANTAGE_MCP_USER_EMAIL to an active user's email")
    return u


def _deal(db, user: User, deal_id: str, perm: Perm) -> Deal:
    if not has_perm(user.role, perm) or not db.query(DealMember).filter_by(deal_id=deal_id, user_id=user.id).first():
        raise PermissionError("Deal not found")
    return db.get(Deal, deal_id)


def _audit(db, user: User, tool: str, resource: str) -> None:
    write_audit(db, user_id=user.id, user_email=user.email, action=f"mcp_{tool}", resource=resource)


@server.tool()
def list_deals() -> list[dict]:
    """Deals the configured user is a member of, with data classification and latest risk score."""
    init_db()
    with SessionLocal() as db:
        u = _user(db)
        ids = [m.deal_id for m in db.query(DealMember).filter_by(user_id=u.id)]
        _audit(db, u, "list_deals", "deals")
        return [{"deal_id": d.id, "name": d.name, "classification": d.data_classification,
                 "period_end": d.reporting_period_end.isoformat() if d.reporting_period_end else None,
                 "risk_score": d.risk_score} for d in db.query(Deal).filter(Deal.id.in_(ids))]


@server.tool()
def search_data_room(deal_id: str, query: str, k: int = 5) -> list[dict]:
    """Hybrid (dense + BM25) search over one deal's documents. Returns cited passages."""
    with SessionLocal() as db:
        u = _user(db)
        _deal(db, u, deal_id, Perm.ASK)
        _audit(db, u, "search_data_room", f"deal:{deal_id}")
    q = guard_question(query).text
    return [h.citation() | {"text": h.chunk.text} for h in HybridRetriever(deal_id).search(q, k=min(k, 10))]


@server.tool()
def get_financials(deal_id: str, fiscal_year: int | None = None) -> list[dict]:
    """Reported and calculated financial values with provenance (XBRL tag, accession, formula, inputs)."""
    with SessionLocal() as db:
        u = _user(db)
        _deal(db, u, deal_id, Perm.DEAL_READ)
        _audit(db, u, "get_financials", f"deal:{deal_id}")
        q = db.query(FinancialFact).filter_by(deal_id=deal_id)
        if fiscal_year:
            q = q.filter_by(fiscal_year=fiscal_year)
        return [{"metric": f.metric, "fiscal_year": f.fiscal_year, "value": f.value, "display": fmt(f.value, f.unit),
                 "kind": f.kind, "status": f.status, "xbrl_tag": f.xbrl_tag, "accession": f.accession,
                 "formula": f.formula, "source_document": f.source_document} for f in q.all()]


@server.tool()
def test_covenants(net_leverage_x: float, interest_coverage_x: float,
                   max_net_leverage: float = 3.5, min_interest_coverage: float = 3.0) -> list[dict]:
    """Test leverage and interest-coverage covenants and report headroom."""
    return covenant_test({"net_leverage_x": net_leverage_x, "interest_coverage_x": interest_coverage_x},
                         max_net_leverage, min_interest_coverage)


@server.tool()
def scan_contract_clauses(text: str) -> list[dict]:
    """Detect high-risk contract clauses (change of control, termination for convenience, MFN, ...)."""
    clean, _ = redact_pii(text[:50_000])
    return [h for h in scan_clauses(clean) if h["source"] == "rule"]


if __name__ == "__main__":
    import sys
    if any(a in sys.argv for a in ("--http", "--sse", "--streamable-http")):
        # This server authenticates nobody: it acts as VANTAGE_MCP_USER_EMAIL. Exposing it on a network port would
        # let anyone who can reach the port read that user's deals. Local stdio only.
        sys.exit("Refused: the Vantage MCP server runs over local stdio only (no network authentication).")
    server.run()
