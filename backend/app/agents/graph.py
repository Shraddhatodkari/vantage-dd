"""LangGraph orchestration — supervisor / parallel specialists / red team / quality gate / HITL.

    START → supervisor ─┬─► financial_analyst ─┐
                        ├─► legal_counsel ─────┤   parallel fan-out (Send), fan-in via reducers
                        ├─► market_strategist ─┤
                        └─► esg_compliance ────┘
                                               ▼
                                 red_team → quality_gate ─┬─ incomplete ─► END (not reviewable)
                                                          └─► human_review ⏸ (interrupt) → END
The IC memo is rendered by the service from the persisted, approved findings — never from
in-memory state — so the exported memo always matches the approved version.

Checkpoints are persisted in SQLite (langgraph-checkpoint-sqlite), so a run paused for partner review
survives an API restart.
"""
from __future__ import annotations

import sqlite3
from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.agents import nodes
from app.agents.state import DDState
from app.core.config import get_settings


def fan_out(state: DDState) -> list[Send]:
    return [Send(agent, state) for agent in state.get("plan", ["financial_analyst"])]


def build_graph(checkpointer=None):
    g = StateGraph(DDState)
    g.add_node("supervisor", nodes.supervisor)
    for s in nodes.SPECIALISTS:
        g.add_node(s, getattr(nodes, s))
    g.add_node("red_team", nodes.red_team)
    g.add_node("quality_gate", nodes.quality_gate)
    g.add_node("human_review", nodes.human_review)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", fan_out, nodes.SPECIALISTS)
    for s in nodes.SPECIALISTS:
        g.add_edge(s, "red_team")
    g.add_edge("red_team", "quality_gate")
    g.add_conditional_edges("quality_gate", nodes.route_after_gate, {"human_review": "human_review", "__end__": END})
    g.add_edge("human_review", END)
    return g.compile(checkpointer=checkpointer)


def _sqlite_checkpointer():
    from langgraph.checkpoint.sqlite import SqliteSaver
    path = get_settings().checkpoint_db
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


@lru_cache
def get_graph():
    return build_graph(_sqlite_checkpointer())
