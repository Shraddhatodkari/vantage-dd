# clause-risk LoRA adapter

* Base model: `distilroberta-base` (downloaded from Hugging Face on first use)
* Method: LoRA (PEFT), r=16, alpha=32, all linear layers + classification head; 1.92M trainable params (2.3% of 84M)
* Training: `python ml/finetune/train_lora.py --epochs 10 --lr 5e-4`, CPU (2 cores), about 4 minutes
* Data: synthetic, template-generated clause sentences (`ml/finetune/data`, dataset hash f4e67156058e)
* Model selection: validation on templates held out from train (group split); test split scored once
* **Test macro-F1 on held-out templates (unseen phrasings): 0.792**, vs 0.62 for the TF-IDF baseline on the same split.
  Reload verified: the saved adapter reproduces 0.792.
* Caveat: the test set is small (56 sentences, 7 labels) and synthetic. Validate on real contract clauses before relying on it.
* Enable in the API with `VANTAGE_CLAUSE_MODEL=lora` (needs `ml/requirements-ml.txt`). Labels: `labels.json`.
