"""MLflow integration: every agent run is an MLflow run.

Logged per run: params (LLM provider/model, embedding provider, prompt version, deal type),
metrics (findings by severity, groundedness rate, guardrail interventions, per-agent latency,
risk score) and the IC memo as an artifact. This gives the team run-over-run comparability when
prompts, models or retrieval settings change — the core of LLMOps.
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from app.core.config import get_settings

log = logging.getLogger("vantage.mlops")
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")


def log_agent_run(run_id: str, params: dict, metrics: dict, report_md: str | None = None,
                  tags: dict | None = None) -> str | None:
    s = get_settings()
    if not s.mlflow_enabled:
        return None
    try:
        import mlflow
        mlflow.set_tracking_uri(s.mlflow_tracking_uri)
        mlflow.set_experiment(s.mlflow_experiment)
        with mlflow.start_run(run_name=f"dd-{run_id[:8]}") as r:
            mlflow.set_tags({"vantage_run_id": run_id, **(tags or {})})
            mlflow.log_params(params)
            mlflow.log_metrics({k: float(v) for k, v in metrics.items() if isinstance(v, (int, float))})
            if report_md:
                with tempfile.TemporaryDirectory() as d:
                    p = Path(d) / "ic_memo.md"
                    p.write_text(report_md, encoding="utf-8")
                    mlflow.log_artifact(str(p))
            return r.info.run_id
    except Exception as exc:  # noqa: BLE001 — tracking must never break the product path
        log.warning("MLflow logging skipped: %s", exc)
        return None
