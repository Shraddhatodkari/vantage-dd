"""Validation of LLM answers to data-room questions.

An AI-written answer is shown only if it is grounded in the retrieved passages:
  * it cites at least one passage, and every citation [n] refers to a passage that was actually provided;
  * every sentence containing a number carries a citation;
  * every number in the answer (other than years and the citation markers) appears in a cited passage.
An explicit "the sources do not say" answer is accepted as an abstention. Anything else is withheld and the
user gets the extractive passages instead, with the reason. The LLM can therefore not add figures or claims
that are not in the cited text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.agents.quality import _close, _numbers

_CITE = re.compile(r"\[(\d{1,2})\]")
_ABSTAIN = re.compile(r"(?:sources?|passages?|documents?)\s+(?:provided\s+)?(?:do|does)\s+not\s+(?:contain|say|state|"
                      r"mention|include)|cannot (?:be )?answer|not (?:stated|disclosed|found) in the (?:sources|passages)", re.I)
_SENT = re.compile(r"(?<=[.!?])\s+")


@dataclass
class QAResult:
    ok: bool
    answer_type: str          # llm_grounded | abstained | extractive
    reason: str | None = None


def _plain_numbers(text: str) -> set[float]:
    text = _CITE.sub(" ", text)
    text = re.sub(r"\b(?:FY)?(?:19|20)\d{2}\b", " ", text)
    return _numbers(text)


def validate_answer(answer: str | None, passages: list[str]) -> QAResult:
    if answer is None or not answer.strip():
        return QAResult(False, "extractive", "no AI answer available (offline mode or provider failure)")
    a = answer.strip()
    cited = [int(n) for n in _CITE.findall(a)]
    if _ABSTAIN.search(a) and not _plain_numbers(a):
        return QAResult(True, "abstained", None)
    if not cited:
        return QAResult(False, "extractive", "AI answer withheld: it cites no source passage")
    bad = sorted({n for n in cited if not 1 <= n <= len(passages)})
    if bad:
        return QAResult(False, "extractive", f"AI answer withheld: it cites passages that were not provided {bad}")
    for s in _SENT.split(a):
        if _plain_numbers(s) and not _CITE.search(s):
            return QAResult(False, "extractive", "AI answer withheld: a sentence with a figure has no citation")
    source_nums = set().union(*(_numbers(passages[n - 1]) for n in set(cited)))
    unsupported = sorted(n for n in _plain_numbers(a) if not any(_close(n, x) for x in source_nums))
    if unsupported:
        return QAResult(False, "extractive", f"AI answer withheld: figures not found in the cited passages {unsupported[:5]}")
    return QAResult(True, "llm_grounded", None)
