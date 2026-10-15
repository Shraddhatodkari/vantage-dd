"""Offline evaluation harness + CI quality gate for the multi-agent pipeline.

Runs the real pipeline (offline LLM mode) on: two illustrative synthetic deals with planted issues, the
Yellow Corp FY2022 10-K (real; rules written with knowledge of it), Old Dominion FY2022 (real, held out) and a
clean illustrative control. Uses the committed SEC/GLEIF/FRED source snapshot — no network needed.

Gates: issue recall >= 0.90, quality-gate rejection rate <= 0.10, 0 critical findings on clean/held-out cases,
score bands respected. Exit code 1 on regression.
Usage: python ml/eval/run_eval.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATES = {"issue_recall": 0.90, "max_rejection_rate": 0.10, "clean_critical_fp": 0}


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="vantage-eval-"))
    os.environ.update({"VANTAGE_ENV": "test", "VANTAGE_DEMO_MODE": "true", "VANTAGE_SEED_PASSWORD": "Eval-Only#Pass2026",
                       "VANTAGE_DATABASE_URL": f"sqlite:///{tmp / 'eval.db'}", "VANTAGE_CHECKPOINT_DB": str(tmp / "cp.db"),
                       "VANTAGE_VECTOR_INDEX_DIR": str(tmp / "vec"), "VANTAGE_STORAGE_DIR": str(tmp / "st"),
                       "VANTAGE_MLFLOW_ENABLED": "false", "VANTAGE_SOURCE_MODE": "snapshot",
                       "VANTAGE_LLM_PROVIDER": os.getenv("VANTAGE_LLM_PROVIDER", "offline"), "MLFLOW_DISABLE_AGENT_HINT": "1"})
    sys.path.insert(0, str(ROOT / "backend"))
    from app.agents.prompts import PROMPT_VERSION
    from app.agents.service import METHODOLOGY, create_run, execute_run
    from app.analytics.financials import store_csv_facts
    from app.db.models import AnalysisRun, Deal, DealMember, Document, User
    from app.db.seed import init_db, seed_demo
    from app.db.session import SessionLocal
    from app.rag.ingest import ingest_text

    init_db()
    seed_demo()
    db = SessionLocal()
    analyst = db.query(User).filter_by(role="analyst").first()
    golden = json.loads((Path(__file__).resolve().parent / "golden.json").read_text(encoding="utf-8"))
    results, exp_total, hit_total, cand_total, rej_total, clean_fp = [], 0, 0, 0, 0, 0
    for case in golden["cases"]:
        deal = db.query(Deal).filter_by(name=case["name"]).first()
        if deal is None and case.get("path"):
            deal = Deal(name=case["name"], target_company="Aurora (fictional)", deal_type="m_and_a", sector="Software",
                        data_classification="illustrative", owner_id=analyst.id)
            db.add(deal)
            db.flush()
            db.add(DealMember(deal_id=deal.id, user_id=analyst.id))
            for p in sorted((ROOT / case["path"]).iterdir()):
                text = p.read_text(encoding="utf-8")
                if p.suffix == ".csv":
                    store_csv_facts(db, deal, text, p.name)
                res = ingest_text(deal.id, uuid.uuid4().hex, p.name, text, "financials" if p.suffix == ".csv" else None)
                db.add(Document(id=res.doc_id, deal_id=deal.id, filename=p.name, doc_type=res.doc_type, sha256=res.sha256,
                                n_chars=res.n_chars, n_chunks=res.n_chunks, data_classification="illustrative"))
            db.commit()
        if deal is None:   # never substitute another company: an unknown case is a configuration error
            raise SystemExit(f"EVAL CONFIG ERROR: golden case {case['name']!r} matches no seeded deal and has no fixture "
                             f"path. Seeded deals: {sorted(d.name for d in db.query(Deal))}. (On Windows this used to "
                             "happen when golden.json was read without UTF-8.)")
        want = "verified_real" if case["kind"].startswith("verified_real") else "illustrative"
        if deal.data_classification != want:
            raise SystemExit(f"EVAL CONFIG ERROR: case {case['name']!r} is {case['kind']} but the deal is "
                             f"{deal.data_classification}; real and illustrative data must not be mixed.")
        t0 = time.perf_counter()
        run = create_run(db, deal, "Full due diligence", analyst.id)
        execute_run(run.id)
        db.expire_all()
        run = db.get(AnalysisRun, run.id)
        acc = [f for f in run.findings if f.verification_status != "rejected"]
        rej = [f for f in run.findings if f.verification_status == "rejected"]
        codes = {f.code for f in acc}
        missed = [c for c in case["must_catch"] if c not in codes]
        n_crit = sum(f.severity == "critical" for f in acc)
        exp_total += len(case["must_catch"])
        hit_total += len(case["must_catch"]) - len(missed)
        cand_total += len(run.findings)
        rej_total += len(rej)
        if "max_critical" in case:
            clean_fp += max(0, n_crit - case["max_critical"])
        score = run.risk_score or 0
        in_band = score >= case.get("min_risk_score", 0) and score <= case.get("max_risk_score", 100)
        results.append({"case": case["name"], "kind": case["kind"], "status": run.status, "risk_score": run.risk_score,
                        "in_band": in_band, "missed": missed, "accepted": len(acc), "rejected": len(rej),
                        "rejected_titles": [f.title for f in rej], "critical": n_crit,
                        "latency_ms": int((time.perf_counter() - t0) * 1000)})
    # ---- blind benchmark: REPORTED, not gating (pre-registered policy in golden.json); runs must still complete
    blind, bands = [], golden.get("blind_benchmark", {})
    for case in bands.get("cases", []):
        deal = db.query(Deal).filter_by(name=case["name"]).first()
        if deal is None or deal.data_classification != "verified_real":
            raise SystemExit(f"EVAL CONFIG ERROR: blind case {case['name']!r} is not a seeded verified-real deal")
        run = create_run(db, deal, "Full due diligence", analyst.id)
        execute_run(run.id)
        db.expire_all()
        run = db.get(AnalysisRun, run.id)
        acc = [f for f in run.findings if f.verification_status != "rejected"]
        n_crit, score = sum(f.severity == "critical" for f in acc), run.risk_score or 0
        met = score >= 55 if case["expected"] == "elevated" else (score <= 30 and n_crit == 0)
        blind.append({"case": case["name"], "expected": case["expected"], "status": run.status, "risk_score": run.risk_score,
                      "recommendation": run.recommendation, "critical": n_crit, "expectation_met": met,
                      "findings": sorted(f.code for f in acc), "outcome_after_cutoff": case["outcome_after_cutoff"]})
    summary = {"issue_recall": round(hit_total / max(exp_total, 1), 3),
               "rejection_rate": round(rej_total / max(cand_total, 1), 3), "clean_critical_fp": clean_fp,
               "prompt_version": PROMPT_VERSION, "methodology": METHODOLOGY, "golden_version": golden["version"]}
    passed = (summary["issue_recall"] >= GATES["issue_recall"] and summary["rejection_rate"] <= GATES["max_rejection_rate"]
              and clean_fp <= GATES["clean_critical_fp"]
              and all(r["in_band"] and r["status"] == "completed" for r in results)
              and all(b["status"] == "completed" for b in blind))
    summary["blind_expectations_met"] = f"{sum(b['expectation_met'] for b in blind)}/{len(blind)}"
    report = {"summary": summary, "gates": GATES, "passed": passed, "cases": results, "notes": golden["notes"],
              "blind_benchmark": {"policy": bands.get("policy"), "results": blind}}
    (Path(__file__).resolve().parent / "eval_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    try:
        import mlflow
        mlflow.set_tracking_uri(os.getenv("VANTAGE_MLFLOW_TRACKING_URI", f"sqlite:///{ROOT / 'mlflow.db'}"))
        mlflow.set_experiment("vantage-dd-eval")
        with mlflow.start_run(run_name=f"eval-{PROMPT_VERSION}"):
            mlflow.log_params({"prompt_version": PROMPT_VERSION, "methodology": METHODOLOGY,
                               "golden_version": golden["version"]})
            mlflow.log_metrics({k: v for k, v in summary.items() if isinstance(v, (int, float))})
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] MLflow logging skipped: {exc}")
    print("QUALITY GATE:", "PASSED" if passed else "FAILED")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
