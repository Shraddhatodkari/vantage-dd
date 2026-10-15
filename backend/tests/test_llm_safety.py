"""LLM failure handling and grounding, with a fake chat model (no API key, no network).
MOCKED: these tests prove the safety logic; they say nothing about the quality of a real LLM."""
from __future__ import annotations

import pytest
from app.agents import llm as llm_mod
from app.agents.llm import LLMFinding, LLMFindings
from app.agents.qa import validate_answer

from .conftest import deal_by, wait_run

P = ["The Company had $1,554.5 million of debt outstanding at December 31, 2022.",
     "The term loan matures in June 2024."]


@pytest.mark.parametrize("answer,ok,kind", [
    ("Debt outstanding was $1,554.5 million [1]. The term loan matures in June 2024 [2].", True, "llm_grounded"),
    ("Debt outstanding was $1,800.0 million [1].", False, "extractive"),           # figure not in the source
    ("Debt outstanding was $1,554.5 million.", False, "extractive"),               # no citation
    ("Debt outstanding was $1,554.5 million [3].", False, "extractive"),           # citation to a passage not given
    ("Debt was $1,554.5 million [1]. Leverage is 9.9x.", False, "extractive"),     # uncited sentence with a figure
    ("The sources provided do not contain the covenant level.", True, "abstained"),
    ("", False, "extractive"),
    (None, False, "extractive"),
])
def test_answer_validation(answer, ok, kind):
    r = validate_answer(answer, P)
    assert (r.ok, r.answer_type) == (ok, kind), r.reason


class _FakeModel:
    def __init__(self, behaviour):
        self.behaviour = behaviour

    def with_structured_output(self, schema):
        return self

    def invoke(self, _msgs):
        if self.behaviour == "raise":
            raise TimeoutError("provider timed out")
        if self.behaviour == "malformed":
            return {"findings": "not a list"}
        if self.behaviour == "hallucinate":
            return LLMFindings(findings=[LLMFinding(category="financial", severity="critical",
                                                    title="Fabricated going-concern warning",
                                                    detail="Auditors issued a going-concern opinion with $9,999 million losses.",
                                                    quotes=["The auditors expressed substantial doubt about going concern."])])
        raise AssertionError(self.behaviour)


def _offline_run(analyst, name):
    deal = deal_by(analyst, name)
    return wait_run(analyst, analyst.post(f"/api/v1/deals/{deal['id']}/runs", json={}).json()["id"])


@pytest.mark.parametrize("behaviour", ["raise", "malformed"])
def test_llm_failure_degrades_to_deterministic_baseline(analyst, monkeypatch, behaviour):
    base = _offline_run(analyst, "Old Dominion")
    monkeypatch.setattr(llm_mod, "get_chat_model", lambda: _FakeModel(behaviour))
    run = _offline_run(analyst, "Old Dominion")
    assert run["status"] == "completed"                            # failure is not fatal and not hidden
    cov = {c["agent"]: c for c in run["coverage"]}
    assert cov["financial_analyst"]["llm"] == "failed" and "LLM review failed" in cov["financial_analyst"]["limitation"]
    assert "failed" in run["metrics"]["llm_status"]
    assert sorted(f["code"] for f in run["findings"]) == sorted(f["code"] for f in base["findings"])
    assert run["risk_score"] == base["risk_score"]


def test_hallucinated_llm_finding_is_rejected_by_the_gate(analyst, monkeypatch):
    monkeypatch.setattr(llm_mod, "get_chat_model", lambda: _FakeModel("hallucinate"))
    run = _offline_run(analyst, "Yellow")
    fab = [f for f in run["findings"] if f["title"] == "Fabricated going-concern warning"]
    assert fab and all(f["verification_status"] == "rejected" for f in fab)
    assert {c["llm"] for c in run["coverage"]} >= {"ok"}


def test_ask_withholds_ungrounded_llm_answer(analyst, monkeypatch):
    import app.api.routes_deals as rd
    deal = deal_by(analyst, "Yellow")
    monkeypatch.setattr(rd, "text_call", lambda *a, **k: "Leverage is 12.5x and the company is insolvent [1].")
    r = analyst.post(f"/api/v1/deals/{deal['id']}/ask", json={"question": "What is the leverage?"}).json()
    assert r["answer_type"] == "extractive" and "12.5" in r["withheld_reason"] and r["citations"]
    monkeypatch.setattr(rd, "text_call", lambda *a, **k: "The passages provided do not contain that information.")
    r = analyst.post(f"/api/v1/deals/{deal['id']}/ask", json={"question": "Who is the CFO's spouse?"}).json()
    assert r["answer_type"] == "abstained"
    monkeypatch.setattr(rd, "text_call", lambda *a, **k: None)     # offline / provider failure
    r = analyst.post(f"/api/v1/deals/{deal['id']}/ask", json={"question": "What is the leverage?"}).json()
    assert r["answer_type"] == "extractive" and r["answer"].startswith("Most relevant passages")


def test_ai_status_reports_rules_only_honestly(analyst, admin, monkeypatch):
    st = analyst.get("/api/v1/ai/status").json()
    assert st["mode"] == "rules_only" and st["provider"] == "offline" and st["api_key_set"] is False
    from app.core.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "llm_provider", "anthropic")
    monkeypatch.setattr(s, "anthropic_api_key", None)
    st = analyst.get("/api/v1/ai/status").json()
    assert st["mode"] == "rules_only" and "no API key" in st["note"]
    monkeypatch.setattr(s, "anthropic_api_key", "sk-test-secret-value")
    monkeypatch.setattr(llm_mod, "get_chat_model", lambda: _FakeModel("raise"))
    st = analyst.get("/api/v1/ai/status").json()
    assert st["mode"] == "llm_configured" and "sk-test-secret-value" not in str(st)
    assert st["max_calls_per_run"] == 5


def test_ai_connectivity_check_is_admin_only_and_safe(analyst, admin, monkeypatch):
    assert analyst.post("/api/v1/admin/ai/check").status_code == 403
    assert admin.post("/api/v1/admin/ai/check").json() == {"ok": False, "status": "not_configured"}
    monkeypatch.setattr(llm_mod, "get_chat_model", lambda: _FakeModel("raise"))
    r = admin.post("/api/v1/admin/ai/check").json()
    assert r == {"ok": False, "status": "failed", "error_type": "TimeoutError"}     # no provider message echoed

    class _Ok:
        def invoke(self, _m):
            return "OK"
    monkeypatch.setattr(llm_mod, "get_chat_model", lambda: _Ok())
    assert admin.post("/api/v1/admin/ai/check").json()["ok"] is True
    acts = [e for e in admin.get("/api/v1/admin/audit?limit=2000").json() if e["action"] == "ai_connectivity_check"]
    assert len(acts) >= 3
