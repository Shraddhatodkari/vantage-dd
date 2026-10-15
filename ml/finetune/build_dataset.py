"""Build the clause-risk classification dataset.

Synthetic, template-driven data with heavy paraphrasing so the model learns the *concept* of each
clause family rather than keywords (rules already cover keywords). Deterministic seed => the
dataset is versioned by content hash, which is logged to MLflow with every training run.

Usage: python ml/finetune/build_dataset.py
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

OUT = Path(__file__).parent / "data"
SEED = 7

PARTIES = ["the Customer", "the Buyer", "Licensee", "the Client", "the Purchaser", "the Distributor", "Acme Corp"]
COUNTERPARTIES = ["the Supplier", "the Vendor", "the Company", "the Service Provider", "Licensor", "the Seller"]
DAYS = ["30", "45", "60", "90", "120"]

TEMPLATES: dict[str, list[str]] = {
    "change_of_control": [
        "Upon a change of control of {cp}, {p} may terminate this Agreement with immediate effect.",
        "If {cp} is acquired, merges with another entity, or sells a controlling stake, {p} may terminate.",
        "Any acquisition of control of {cp} by a third party shall constitute a default under this Agreement.",
        "If more than 50% of the voting shares of {cp} are acquired by a third party, {p} may terminate this Agreement.",
        "Any transfer of a controlling interest in {cp} shall entitle {p} to end this Agreement forthwith.",
        "A merger, consolidation or sale of substantially all assets of {cp} requires the prior approval of {p}.",
        "Should {cp} come under the control of a competitor of {p}, this Agreement may be cancelled immediately.",
        "In the event {cp} undergoes a change in ownership, all outstanding amounts become immediately due and payable.",
    ],
    "termination_for_convenience": [
        "{p} may terminate this Agreement for convenience on {d} days' notice.",
        "{p} may terminate at any time without cause and without liability upon {d} days written notice.",
        "Without prejudice to other rights, {p} may terminate this Agreement for any reason or no reason.",
        "{p} may end this Agreement at any time, for any reason, upon {d} days' written notice.",
        "Either party may cancel this contract without cause by giving {d} days notice to the other.",
        "{p} reserves the right to discontinue the services at its sole discretion on {d} days prior notice.",
        "This Agreement may be terminated by {p} without penalty and without the need to state a reason.",
    ],
    "most_favoured_nation": [
        "{cp} shall offer {p} most favoured customer pricing, no less favourable than any other customer receives.",
        "The prices charged to {p} shall at all times be the lowest prices charged by {cp} to any customer.",
        "If {cp} grants any other customer more favourable prices, {p} shall be entitled to the same prices.",
        "{cp} warrants that the prices charged to {p} are no higher than those offered to any other customer.",
        "If {cp} offers lower pricing to any third party, it shall extend the same pricing to {p} retroactively.",
        "{cp} shall ensure {p} receives terms at least as favourable as those granted to any comparable client.",
    ],
    "assignment_restriction": [
        "{cp} may not assign this Agreement without the prior written consent of {p}.",
        "This Agreement shall not be assigned or transferred by either party without prior written consent.",
        "No assignment of this Agreement, including by merger or operation of law, is permitted without consent.",
        "Neither party may transfer its rights or obligations hereunder without the other party's written approval.",
        "{cp} shall not delegate or transfer this Agreement, whether voluntarily or by operation of law, absent consent of {p}.",
        "Any purported transfer of this Agreement without {p}'s approval shall be null and void.",
    ],
    "unlimited_liability": [
        "{cp} shall be fully liable for all losses, without limitation of liability.",
        "Nothing in this Agreement limits the liability of {cp}, which shall be unlimited.",
        "{cp} is liable for all chargebacks, fines and penalties without any cap on liability.",
        "{cp} shall indemnify {p} for all losses of whatever nature, without any cap or limitation.",
        "The limitations of liability in this Agreement shall not apply to {cp}'s obligations, which are uncapped.",
        "{cp} assumes full responsibility for every claim, fine and penalty arising from its sub-contractors.",
    ],
    "exclusivity": [
        "{cp} grants {p} exclusive rights in the Territory and shall not appoint any other distributor.",
        "{p} shall purchase exclusively from {cp} and shall not source the Products from any other supplier.",
        "During the Term, {cp} shall exclusively supply {p} and shall not supply any competitor of {p}.",
        "{cp} shall not provide similar services to any other party in the Territory during the Term.",
        "{p} agrees to purchase all of its requirements for the Products solely from {cp}.",
        "During the Term {cp} will act as the sole and only provider of logistics services to {p}.",
    ],
    "benign": [
        "{cp} shall provide the services with reasonable skill and care.",
        "Payment shall be made by bank transfer to the account notified by {cp}.",
        "The parties shall cooperate in good faith to resolve any dispute.",
        "This Agreement shall be governed by the laws of the State of New York.",
        "All notices shall be in writing and delivered to the addresses set out in Schedule 1.",
        "{cp} shall deliver the monthly service report within ten business days after month end.",
        "Invoices are payable within {d} days of receipt by {p}.",
        "Headings are for convenience only and do not affect interpretation.",
        "Each party shall bear its own costs in connection with the negotiation of this Agreement.",
        "This Agreement may be executed in counterparts, each of which is deemed an original.",
        "{cp} shall maintain insurance with reputable insurers in amounts customary in the industry.",
        "The parties shall meet quarterly to review service levels and continuous improvement initiatives.",
        "Capitalised terms not defined herein have the meanings given in the Master Agreement.",
    ],
}


def _augment(s: str, rng: random.Random) -> str:
    if rng.random() < 0.3:
        s = s.replace("shall", "will")
    if rng.random() < 0.2:
        s = "Notwithstanding anything to the contrary, " + s[0].lower() + s[1:]
    if rng.random() < 0.15:
        s = s.upper() if rng.random() < 0.3 else s
    return s


def build(n_per_template: int = 8) -> tuple[list[dict], list[dict]]:
    rng = random.Random(SEED)  # nosec B311 - dataset shuffling, not security
    rows = []
    for label, temps in TEMPLATES.items():
        for t_idx, t in enumerate(temps):
            for _ in range(n_per_template):
                text = t.format(p=rng.choice(PARTIES), cp=rng.choice(COUNTERPARTIES), d=rng.choice(DAYS))
                rows.append({"text": _augment(text, rng), "label": label, "template": f"{label}:{t_idx}"})
    rng.shuffle(rows)
    # Hold out one whole template per label for test => measures generalisation to unseen phrasing,
    # not memorisation of templates.
    held = {f"{label}:{len(temps) - 1}" for label, temps in TEMPLATES.items()}
    train = [r for r in rows if r["template"] not in held]
    test = [r for r in rows if r["template"] in held]
    return train, test


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    train, test = build()
    for name, rows in (("train", train), ("test", test)):
        with (OUT / f"clauses_{name}.jsonl").open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    digest = hashlib.sha256((OUT / "clauses_train.jsonl").read_bytes()).hexdigest()[:12]
    print(f"train={len(train)} test={len(test)} dataset_hash={digest}")


if __name__ == "__main__":
    main()
