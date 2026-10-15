"""Parameter-efficient fine-tuning (LoRA / QLoRA) of a transformer clause-risk classifier.

Why fine-tune? The TF-IDF baseline reaches ~0.62 macro-F1 on *unseen phrasings* (held-out
templates) because it keys on surface words. A fine-tuned encoder learns clause semantics.
LoRA trains <1% of parameters, so it runs on a single consumer GPU or a free Colab T4.

Tracks everything in MLflow and registers the model only if it beats the baseline on the same split.

Install:  pip install -r ml/requirements-ml.txt
Run:      python ml/finetune/train_lora.py --model distilroberta-base --epochs 10 --lr 5e-4
QLoRA:    python ml/finetune/train_lora.py --model meta-llama/Llama-3.2-1B --qlora   (needs CUDA + bitsandbytes)
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).parent / "data"
BASELINE_MACRO_F1 = 0.62


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="distilroberta-base")
    ap.add_argument("--revision", default="main",
                    help="model-hub revision; pin a commit hash for a reproducible, tamper-resistant download")
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--alpha", type=int, default=32)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--qlora", action="store_true", help="4-bit quantised base model (CUDA only)")
    ap.add_argument("--out", default=str(ROOT / "ml" / "artifacts" / "clause_lora"))
    args = ap.parse_args()

    import mlflow
    import numpy as np
    import torch
    from datasets import Dataset
    from peft import (
        LoraConfig,
        TaskType,
        get_peft_model,
        prepare_model_for_kbit_training,
    )
    from sklearn.metrics import f1_score
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        DataCollatorWithPadding,
        Trainer,
        TrainingArguments,
    )

    rows = {s: [json.loads(x) for x in (DATA / f"clauses_{s}.jsonl").read_text(encoding="utf-8").splitlines()] for s in ("train", "test")}
    labels = sorted({r["label"] for r in rows["train"]})
    l2i = {lab: i for i, lab in enumerate(labels)}
    tok = AutoTokenizer.from_pretrained(args.model, revision=args.revision)  # nosec B615 - pin via --revision <commit>
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    def to_ds(rs):
        ds = Dataset.from_list([{"text": r["text"], "label": l2i[r["label"]]} for r in rs])
        return ds.map(lambda b: tok(b["text"], truncation=True, max_length=128), batched=True)

    # Model selection uses a validation split carved from TRAIN by *template* (group split), so the
    # selected checkpoint is the one that generalises to unseen phrasings. The held-out-template TEST
    # split is scored exactly once at the end, so the reported number is not tuned on.
    tr = rows["train"]
    val_templates = {}
    for r in tr:  # second-to-last template of each label goes to validation
        val_templates.setdefault(r["label"], set()).add(r["template"])
    val_set = {sorted(v, key=lambda t: int(t.split(":")[1]))[-1] for v in val_templates.values()}
    train_ds = to_ds([r for r in tr if r["template"] not in val_set])
    val_ds = to_ds([r for r in tr if r["template"] in val_set])
    test_ds = to_ds(rows["test"])

    quant = {}
    if args.qlora:
        from transformers import BitsAndBytesConfig
        quant = {"quantization_config": BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                                           bnb_4bit_compute_dtype=torch.bfloat16,
                                                           bnb_4bit_use_double_quant=True), "device_map": "auto"}
    model = AutoModelForSequenceClassification.from_pretrained(  # nosec B615 - pin via --revision <commit>
        args.model, revision=args.revision, num_labels=len(labels), id2label=dict(enumerate(labels)), label2id=l2i, **quant)
    model.config.pad_token_id = tok.pad_token_id
    if args.qlora:
        model = prepare_model_for_kbit_training(model)
    # RoBERTa-family encoders have no randomly initialised pooler (unlike DeBERTa-v3), so the saved adapter
    # (LoRA weights + classification head) reproduces training-time predictions exactly on reload.
    model = get_peft_model(model, LoraConfig(task_type=TaskType.SEQ_CLS, r=args.rank, lora_alpha=args.alpha,
                                             lora_dropout=0.1, target_modules="all-linear"))
    model.print_trainable_parameters()

    def metrics(p):
        pred = np.argmax(p.predictions, axis=-1)
        return {"macro_f1": f1_score(p.label_ids, pred, average="macro")}

    mlflow.set_tracking_uri(os.getenv("VANTAGE_MLFLOW_TRACKING_URI", f"sqlite:///{ROOT / 'mlflow.db'}"))
    mlflow.set_experiment("clause-risk-classifier")
    with mlflow.start_run(run_name=f"lora-{args.model.split('/')[-1]}{'-qlora' if args.qlora else ''}"):
        mlflow.log_params(vars(args) | {"n_labels": len(labels), "split": "held-out-template"})
        trainer = Trainer(
            model=model,
            args=TrainingArguments(output_dir=args.out, num_train_epochs=args.epochs, learning_rate=args.lr,
                                   per_device_train_batch_size=args.batch, per_device_eval_batch_size=32,
                                   eval_strategy="epoch", save_strategy="epoch", load_best_model_at_end=True,
                                   metric_for_best_model="macro_f1", report_to=["mlflow"], logging_steps=10,
                                   warmup_steps=max(1, int(0.1 * args.epochs * len(train_ds) / args.batch)),
                                   weight_decay=0.01, seed=7, save_total_limit=1),
            train_dataset=train_ds, eval_dataset=val_ds, processing_class=tok,
            data_collator=DataCollatorWithPadding(tok), compute_metrics=metrics)
        trainer.train()
        f1 = trainer.evaluate(test_ds, metric_key_prefix="test")["test_macro_f1"]
        mlflow.log_metric("final_macro_f1", f1)
        mlflow.log_metric("lift_vs_baseline", f1 - BASELINE_MACRO_F1)
        model.save_pretrained(args.out)
        tok.save_pretrained(args.out)
        (Path(args.out) / "labels.json").write_text(json.dumps(labels), encoding="utf-8")
        if f1 > BASELINE_MACRO_F1:
            mlflow.log_artifacts(args.out, artifact_path="lora_adapter")
            print(f"LoRA macro-F1 {f1:.3f} beats baseline {BASELINE_MACRO_F1} -> adapter logged for promotion")
        else:
            print(f"LoRA macro-F1 {f1:.3f} does not beat baseline; keeping baseline in production")


if __name__ == "__main__":
    main()
