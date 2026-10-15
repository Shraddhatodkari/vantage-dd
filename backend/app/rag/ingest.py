"""Document ingestion: input guardrails -> persist (by document id) -> chunk -> embed -> index.

The stored text is exactly what agents see and what evidence locators point into, so excerpts can be
re-verified at any time against `load_document_text`."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.guardrails.input_guards import guard_document
from app.rag.chunking import chunk_document
from app.rag.embeddings import get_embedder
from app.rag.vectorstore import get_vector_store

DOC_TYPE_HINTS = {
    "financials": ("financial", "income", "balance", "p&l", ".csv"),
    "legal": ("credit", "agreement", "legal", "contract", "litigation", "memo"),
    "market": ("market", "industry", "competit"),
    "esg": ("esg", "sustainab", "governance"),
    "compliance": ("compliance", "aml", "kyc", "pci", "risk_assessment"),
    "management": ("management", "presentation", "cim", "investor", "teaser"),
}


def infer_doc_type(filename: str) -> str:
    f = filename.lower()
    for dtype, hints in DOC_TYPE_HINTS.items():
        if any(h in f for h in hints):
            return dtype
    return "other"


@dataclass
class IngestResult:
    doc_id: str
    filename: str
    doc_type: str
    sha256: str          # of the original (pre-guardrail) text: used for duplicate detection
    n_chars: int
    n_chunks: int
    redactions: int
    injection_hits: list[str]


def _deal_dir(deal_id: str) -> Path:
    p = get_settings().storage_dir / deal_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def document_sha(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def ingest_text(deal_id: str, doc_id: str, filename: str, raw: str, doc_type: str | None = None) -> IngestResult:
    s = get_settings()
    doc_type = doc_type or infer_doc_type(filename)
    guarded = guard_document(raw)
    # Only the guarded (PII-redacted, injection-neutralised) text is persisted and indexed.
    (_deal_dir(deal_id) / f"{doc_id}.txt").write_text(guarded.text, encoding="utf-8")
    chunks = chunk_document(doc_id, filename, doc_type, guarded.text, s.chunk_size, s.chunk_overlap)
    if chunks:
        vecs = get_embedder().embed([c.text for c in chunks])
        get_vector_store().add(deal_id, chunks, vecs)
    return IngestResult(doc_id, filename, doc_type, document_sha(raw), len(guarded.text), len(chunks),
                        guarded.total_redactions, guarded.injection_hits)


def load_document_text(deal_id: str, doc_id: str) -> str | None:
    p = get_settings().storage_dir / deal_id / f"{doc_id}.txt"
    return p.read_text(encoding="utf-8") if p.exists() else None
