"""LLM provider factory + structured-output helpers.

With VANTAGE_LLM_PROVIDER=offline (the default) no LLM is called: specialists run on deterministic
tools + rules only. This keeps CI hermetic, demos free, and gives a non-LLM baseline that the
LLM-enriched pipeline is evaluated against in `ml/eval`.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import get_settings

log = logging.getLogger("vantage.llm")


class LLMFinding(BaseModel):
    category: Literal["financial", "legal", "market", "esg", "compliance", "consistency", "operational"]
    severity: Literal["low", "medium", "high", "critical"]
    title: str
    detail: str
    quotes: list[str] = Field(default_factory=list, description="verbatim sentences copied from the documents")


class LLMFindings(BaseModel):
    findings: list[LLMFinding]


class AgentPlan(BaseModel):
    specialists: list[str]


@lru_cache
def get_chat_model():
    s = get_settings()
    try:
        if s.llm_provider == "anthropic" and s.anthropic_api_key:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(model=s.llm_model, temperature=s.llm_temperature,
                                 api_key=s.anthropic_api_key, max_tokens=2048, timeout=60, max_retries=2)
        if s.llm_provider == "openai" and s.openai_api_key:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=s.llm_model, temperature=s.llm_temperature,
                              api_key=s.openai_api_key, timeout=60, max_retries=2)
    except ImportError as exc:  # provider package not installed
        log.warning("LLM provider unavailable, falling back to offline: %s", exc)
    return None


def structured_call_ex(schema: type[BaseModel], system: str, user: str) -> tuple[BaseModel | None, str]:
    """Invoke the LLM with a pydantic schema. Never raises. Returns (result, status) where status is
    'not_configured' (offline mode), 'ok', or 'failed' (timeout, provider error, invalid/malformed output) —
    so every run records whether the LLM actually contributed."""
    model = get_chat_model()
    if model is None:
        return None, "not_configured"
    try:
        out = model.with_structured_output(schema).invoke(
            [{"role": "system", "content": system}, {"role": "user", "content": user}])
    except Exception as exc:  # noqa: BLE001
        log.warning("structured LLM call failed: %s", type(exc).__name__)   # no message: may echo deal content
        return None, "failed"
    if not isinstance(out, schema):
        log.warning("structured LLM call returned %s, expected %s", type(out).__name__, schema.__name__)
        return None, "failed"
    return out, "ok"


def structured_call(schema: type[BaseModel], system: str, user: str) -> BaseModel | None:
    return structured_call_ex(schema, system, user)[0]


LLM_CALLS_PER_RUN = 5     # supervisor plan + 4 specialists (bounded; no loops) — documented for cost control


def provider_status() -> dict:
    """What the app will actually do — never claims an LLM is in use when it is not."""
    s = get_settings()
    key = {"anthropic": s.anthropic_api_key, "openai": s.openai_api_key}.get(s.llm_provider)
    model = get_chat_model() if s.llm_provider != "offline" else None
    if s.llm_provider == "offline":
        mode, note = "rules_only", "No LLM provider configured: deterministic rules and extractive search only."
    elif not key:
        mode, note = "rules_only", f"Provider '{s.llm_provider}' selected but no API key is set: rules only."
    elif model is None:
        mode, note = "rules_only", f"Provider '{s.llm_provider}' package not installed: rules only."
    else:
        mode, note = "llm_configured", ("LLM configured. Its output is used only after citation and number checks; "
                                        "connectivity is not verified until an administrator runs the check.")
    return {"provider": s.llm_provider, "model": s.llm_model if s.llm_provider != "offline" else None,
            "api_key_set": bool(key), "mode": mode, "note": note, "max_calls_per_run": LLM_CALLS_PER_RUN,
            "max_tokens_per_call": 2048, "timeout_seconds": 60, "max_retries": 2}


def connectivity_check() -> dict:
    """One minimal call (a few tokens) to confirm the provider answers. Errors are reported by type only."""
    import time as _t
    model = get_chat_model()
    if model is None:
        return {"ok": False, "status": "not_configured"}
    t0 = _t.perf_counter()
    try:
        model.invoke([{"role": "user", "content": "Reply with the single word OK."}])
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": "failed", "error_type": type(exc).__name__}
    return {"ok": True, "status": "ok", "latency_ms": int((_t.perf_counter() - t0) * 1000)}


def text_call(system: str, user: str) -> str | None:
    model = get_chat_model()
    if model is None:
        return None
    try:
        return model.invoke([{"role": "system", "content": system}, {"role": "user", "content": user}]).content
    except Exception as exc:  # noqa: BLE001
        log.warning("LLM call failed: %s", type(exc).__name__)
        return None


def compact(obj, limit: int = 3500) -> str:
    s = json.dumps(obj, default=str, indent=1)
    return s if len(s) <= limit else s[:limit] + " ...[truncated]"
