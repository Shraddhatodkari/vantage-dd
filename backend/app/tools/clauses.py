"""Contract clause risk scanner.

Two layers:
1. A precise rule layer (regex) for well-known high-risk clause families.
2. An ML layer — the clause-risk classifier trained in `ml/finetune` (TF-IDF+LR baseline, or the
   LoRA fine-tuned transformer when available) — loaded from the MLflow-registered artifact.
   The ML layer catches paraphrased clauses the rules miss.
"""
from __future__ import annotations

import pickle  # nosec B403 - only for the hash-pinned, repository-shipped model
import re
from functools import lru_cache
from pathlib import Path

from app.core.config import ROOT_DIR

CLAUSE_RULES: dict[str, tuple[str, str]] = {
    "change_of_control": (r"change of control", "high"),
    "termination_for_convenience": (r"terminat\w* (?:for convenience|on \d+ days|immediately)", "high"),
    "most_favoured_nation": (r"most[- ]favou?red[- ]nation", "medium"),
    "assignment_restriction": (r"may not be assigned|without .{0,40}prior written consent", "medium"),
    "mandatory_prepayment": (r"mandatory prepayment|shall immediately prepay", "high"),
    "financial_covenant": (r"shall not permit the .{0,60}ratio", "medium"),
    "unlimited_liability": (r"fully liable|unlimited liability", "high"),
    "reserve_requirement": (r"rolling reserve", "medium"),
    "exclusivity": (r"\bexclusiv", "medium"),
    "auto_renewal": (r"auto-?renew", "low"),
}

ML_MIN_CONFIDENCE = 0.70  # raised from 0.55 after a false positive on a real 10-K
MODEL_PATH = ROOT_DIR / "ml" / "artifacts" / "clause_classifier.pkl"


LORA_PATH = ROOT_DIR / "ml" / "artifacts" / "clause_lora"


class LoraClauseModel:
    """Fine-tuned DistilRoBERTa + LoRA adapter behind the same predict_proba/classes_ interface as
    the scikit-learn baseline, so the scanner does not care which model is active."""

    def __init__(self, path: Path):
        import json

        import torch
        from peft import AutoPeftModelForSequenceClassification
        from transformers import AutoTokenizer
        self.torch = torch
        self.classes_ = json.loads((path / "labels.json").read_text(encoding="utf-8"))
        # local directory only: never fall back to downloading from a model hub
        self.tok = AutoTokenizer.from_pretrained(path, local_files_only=True)  # nosec B615 - local path, no download
        self.model = AutoPeftModelForSequenceClassification.from_pretrained(  # nosec B615 - local path, no download
            path, num_labels=len(self.classes_), local_files_only=True).eval()

    def predict_proba(self, texts: list[str]):
        with self.torch.no_grad():
            enc = self.tok(texts, truncation=True, max_length=128, padding=True, return_tensors="pt")
            return self.torch.softmax(self.model(**enc).logits, dim=-1).numpy()


@lru_cache
def _load_model():
    """VANTAGE_CLAUSE_MODEL = baseline (default, CPU-light) | lora (fine-tuned transformer) | none."""
    import os
    choice = os.getenv("VANTAGE_CLAUSE_MODEL", "baseline")
    if choice == "lora" and (LORA_PATH / "adapter_config.json").exists():
        try:
            return LoraClauseModel(LORA_PATH)
        except Exception as exc:  # noqa: BLE001 — torch/peft not installed -> fall back
            import logging
            logging.getLogger("vantage.clauses").warning("LoRA model unavailable (%s); using baseline", exc)
    if choice != "none" and MODEL_PATH.exists():
        # pickle can execute code: only unpickle the exact artifact whose SHA-256 is pinned in the repository
        import hashlib
        import logging
        data = MODEL_PATH.read_bytes()
        pin = MODEL_PATH.with_name(MODEL_PATH.name + ".sha256")
        expected = pin.read_text(encoding="utf-8").strip() if pin.exists() else None
        if expected is None or hashlib.sha256(data).hexdigest() != expected:
            logging.getLogger("vantage.clauses").error(
                "clause model %s does not match its pinned SHA-256; it was NOT loaded (rule-based scanning only)",
                MODEL_PATH.name)
            return None
        return pickle.loads(data)  # nosec B301 - integrity verified against the pinned hash above
    return None


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.;])\s+(?=[A-Z(])", text) if len(s.strip()) > 20]


def scan_clauses(text: str, use_model: bool = True) -> list[dict]:
    hits: list[dict] = []
    unmatched: list[str] = []
    for sent in _sentences(text):
        matched = False
        for name, (pattern, sev) in CLAUSE_RULES.items():
            m = re.search(pattern, sent, re.IGNORECASE)
            if m:
                # excerpt centred on the match so the quote always shows the triggering language
                start = max(0, m.start() - 120)
                excerpt = ("…" if start else "") + sent[start:m.end() + 260]
                hits.append({"clause": name, "severity": sev, "source": "rule", "text": excerpt,
                             "match": sent[m.start():m.end()]})
                matched = True
        if not matched:
            unmatched.append(sent)
    model = _load_model() if use_model else None
    if model is not None and unmatched:
        probas = model.predict_proba(unmatched)  # one batched call (per-sentence calls were slow on real filings)
        for sent, proba in zip(unmatched, probas, strict=True):
            label = model.classes_[proba.argmax()]
            if label != "benign" and proba.max() >= ML_MIN_CONFIDENCE:
                hits.append({"clause": label, "severity": "medium", "source": "ml",
                             "confidence": round(float(proba.max()), 2), "text": sent[:400], "match": sent[:400]})
    return hits


def extract_covenant_thresholds(text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    m = re.search(r"Leverage Ratio.{0,160}?exceed\s+(\d+\.\d+)\s+to\s+1", text, re.I | re.S)
    if m:
        out["max_net_leverage"] = float(m.group(1))
    m = re.search(r"Interest.{0,160}?less than\s+(\d+\.\d+)\s+to\s+1", text, re.I | re.S)
    if m:
        out["min_interest_coverage"] = float(m.group(1))
    return out
