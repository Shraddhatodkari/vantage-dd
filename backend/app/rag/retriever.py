"""Hybrid retrieval: dense cosine + BM25 lexical, fused with min-max normalised weighted sum,
then de-duplicated with Maximal Marginal Relevance so agents see diverse evidence.

Lexical matching matters in diligence: exact terms like "Change of Control", "3.50 to 1.00"
or "PCI DSS" are often missed by dense embeddings alone.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi

from app.core.config import get_settings
from app.rag.chunking import Chunk
from app.rag.embeddings import get_embedder, tokenize
from app.rag.vectorstore import get_vector_store


@dataclass
class Retrieved:
    chunk: Chunk
    score: float
    dense: float
    lexical: float

    def citation(self) -> dict:
        return {"chunk_id": self.chunk.chunk_id, "filename": self.chunk.filename,
                "doc_type": self.chunk.doc_type, "quote": self.chunk.text[:280]}


def _minmax(x: np.ndarray) -> np.ndarray:
    if x.size == 0:
        return x
    lo, hi = float(x.min()), float(x.max())
    return np.zeros_like(x) if hi - lo < 1e-9 else (x - lo) / (hi - lo)


class HybridRetriever:
    def __init__(self, namespace: str):
        self.ns = namespace
        self.store = get_vector_store()
        self.embedder = get_embedder()
        self.settings = get_settings()

    def search(self, query: str, k: int | None = None, doc_types: list[str] | None = None,
               mmr_lambda: float = 0.7) -> list[Retrieved]:
        k = k or self.settings.top_k
        chunks = self.store.all_chunks(self.ns)
        if doc_types:
            chunks = [c for c in chunks if c.doc_type in doc_types]
        if not chunks:
            return []
        qv = self.embedder.embed([query])[0]
        cv = self.embedder.embed([c.text for c in chunks])
        dense = cv @ qv
        bm25 = BM25Okapi([tokenize(c.text) or ["_"] for c in chunks])
        lexical = np.asarray(bm25.get_scores(tokenize(query)), dtype=np.float32)
        a = self.settings.hybrid_alpha
        fused = a * _minmax(dense) + (1 - a) * _minmax(lexical)

        # MMR re-ranking over the top candidate pool
        pool = list(np.argsort(-fused)[: max(k * 3, 10)])
        selected: list[int] = []
        while pool and len(selected) < k:
            if not selected:
                best = pool[0]
            else:
                sim_to_sel = (cv[pool] @ cv[selected].T).max(axis=1)
                mmr = mmr_lambda * fused[pool] - (1 - mmr_lambda) * sim_to_sel
                best = pool[int(np.argmax(mmr))]
            selected.append(best)
            pool.remove(best)
        return [Retrieved(chunks[i], float(fused[i]), float(dense[i]), float(lexical[i])) for i in selected]
