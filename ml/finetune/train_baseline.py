"""Train the CPU baseline clause-risk classifier (TF-IDF word+char n-grams -> logistic regression),
track it in MLflow, register it in the Model Registry and export the artifact the API loads.

This baseline ships in the product today; `train_lora.py` is the GPU fine-tuning path whose
model is promoted only if it beats this baseline on the held-out template split.

Usage: python ml/finetune/train_baseline.py
"""
from __future__ import annotations

import hashlib
import json
import os
import pickle  # nosec B403 - writes the repository's own artifact
import sys
from pathlib import Path

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import classification_report, f1_score  # noqa: E402
from sklearn.pipeline import FeatureUnion, Pipeline  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).parent / "data"
ARTIFACT = ROOT / "ml" / "artifacts" / "clause_classifier.pkl"
PROMOTION_MIN_MACRO_F1 = 0.60  # on UNSEEN phrasings (held-out templates)


def load(name: str) -> tuple[list[str], list[str]]:
    rows = [json.loads(line) for line in (DATA / f"clauses_{name}.jsonl").read_text(encoding="utf-8").splitlines()]
    return [r["text"] for r in rows], [r["label"] for r in rows]


def main() -> int:
    if not (DATA / "clauses_train.jsonl").exists():
        sys.path.insert(0, str(Path(__file__).parent))
        import build_dataset
        build_dataset.main()
    X_tr, y_tr = load("train")
    X_te, y_te = load("test")
    params = {"C": 4.0, "word_ngrams": (1, 2), "char_ngrams": (3, 5), "class_weight": "balanced"}
    model = Pipeline([
        ("features", FeatureUnion([
            ("word", TfidfVectorizer(ngram_range=params["word_ngrams"], sublinear_tf=True, lowercase=True)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=params["char_ngrams"], sublinear_tf=True)),
        ])),
        ("clf", LogisticRegression(C=params["C"], max_iter=2000, class_weight=params["class_weight"])),
    ])
    model.fit(X_tr, y_tr)
    pred = model.predict(X_te)
    macro_f1 = f1_score(y_te, pred, average="macro")
    report = classification_report(y_te, pred, output_dict=True, zero_division=0)
    print(classification_report(y_te, pred, zero_division=0))

    try:
        import mlflow
        import mlflow.sklearn
        mlflow.set_tracking_uri(os.getenv("VANTAGE_MLFLOW_TRACKING_URI", f"sqlite:///{ROOT / 'mlflow.db'}"))
        mlflow.set_experiment("clause-risk-classifier")
        with mlflow.start_run(run_name="tfidf-logreg-baseline"):
            mlflow.log_params({k: str(v) for k, v in params.items()} | {
                "dataset_hash": hashlib.sha256((DATA / "clauses_train.jsonl").read_bytes()).hexdigest()[:12],
                "n_train": len(X_tr), "n_test": len(X_te), "split": "held-out-template"})
            mlflow.log_metric("macro_f1", macro_f1)
            for label, m in report.items():
                if isinstance(m, dict) and "f1-score" in m and label not in ("macro avg", "weighted avg"):
                    mlflow.log_metric(f"f1_{label}", m["f1-score"])
            if macro_f1 >= PROMOTION_MIN_MACRO_F1:
                mlflow.sklearn.log_model(model, name="model", registered_model_name="clause-risk-classifier",
                                         input_example=X_te[:2])
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] MLflow logging skipped: {exc}")

    if macro_f1 < PROMOTION_MIN_MACRO_F1:
        print(f"Macro-F1 {macro_f1:.3f} below promotion bar {PROMOTION_MIN_MACRO_F1}; artifact NOT exported.")
        return 1
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    with ARTIFACT.open("wb") as fh:
        pickle.dump(model, fh)
    # pin the artifact's hash: the API refuses to unpickle a file that does not match it
    ARTIFACT.with_name(ARTIFACT.name + ".sha256").write_text(hashlib.sha256(ARTIFACT.read_bytes()).hexdigest() + "\n",
                                                             encoding="utf-8")
    print(f"macro_f1={macro_f1:.3f} -> exported {ARTIFACT.relative_to(ROOT)} (+ .sha256 pin)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
