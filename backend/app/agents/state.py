"""Shared LangGraph state. Reducers make parallel specialist branches merge safely."""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class DDState(TypedDict, total=False):
    run_id: str
    deal: dict[str, Any]
    question: str
    plan: list[str]
    findings: Annotated[list[dict], operator.add]        # candidate findings from all agents
    events: Annotated[list[dict], operator.add]
    agent_errors: Annotated[list[dict], operator.add]
    coverage: Annotated[list[dict], operator.add]         # what each specialist actually examined
    validated_findings: list[dict]
    rejected_findings: list[dict]
    incomplete: bool
    risk_score: float | None
    risk_breakdown: dict[str, float]
    recommendation: str
    review: dict[str, Any]
