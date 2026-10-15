"""Explicit permission matrix (no role hierarchy).

Roles are NOT ranked: an admin does not inherit partner approval rights, and a partner does not
inherit user administration. Deal-scoped permissions additionally require deal membership.
See docs/PERMISSIONS.md for the human-readable matrix.
"""
from __future__ import annotations

from enum import Enum

from app.core.security import Role


class Perm(str, Enum):
    DEAL_CREATE = "deal:create"
    DEAL_READ = "deal:read"                # deal-scoped: requires membership
    DEAL_LIST_ALL_METADATA = "deal:list_all_metadata"  # names/status only, no evidence or reports
    DEAL_MANAGE_MEMBERS = "deal:manage_members"
    DOC_UPLOAD = "document:upload"         # deal-scoped
    DOC_DELETE = "document:delete"         # deal-scoped, blocked while a run is awaiting review
    RUN_START = "run:start"                # deal-scoped
    RUN_REVIEW = "run:review"              # deal-scoped; segregation of duties enforced separately
    REPORT_READ = "report:read"            # deal-scoped
    ASK = "ask"                            # deal-scoped
    SOURCE_REFRESH = "source:refresh"      # deal-scoped: re-fetch SEC/GLEIF/FRED
    USER_MANAGE = "user:manage"
    AUDIT_READ = "audit:read"


MATRIX: dict[Role, set[Perm]] = {
    Role.ANALYST: {Perm.DEAL_CREATE, Perm.DEAL_READ, Perm.DOC_UPLOAD, Perm.RUN_START, Perm.REPORT_READ, Perm.ASK},
    Role.PARTNER: {Perm.DEAL_CREATE, Perm.DEAL_READ, Perm.DOC_UPLOAD, Perm.DOC_DELETE, Perm.RUN_START,
                   Perm.RUN_REVIEW, Perm.REPORT_READ, Perm.ASK, Perm.SOURCE_REFRESH, Perm.DEAL_MANAGE_MEMBERS},
    Role.ADMIN: {Perm.USER_MANAGE, Perm.AUDIT_READ, Perm.DEAL_LIST_ALL_METADATA, Perm.DEAL_MANAGE_MEMBERS},
}

DEAL_SCOPED = {Perm.DEAL_READ, Perm.DOC_UPLOAD, Perm.DOC_DELETE, Perm.RUN_START, Perm.RUN_REVIEW,
               Perm.REPORT_READ, Perm.ASK, Perm.SOURCE_REFRESH}


def has_perm(role: str, perm: Perm) -> bool:
    try:
        return perm in MATRIX[Role(role)]
    except ValueError:
        return False


def perms_for(role: str) -> list[str]:
    try:
        return sorted(p.value for p in MATRIX[Role(role)])
    except ValueError:
        return []
