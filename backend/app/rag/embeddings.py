"""Pluggable embedding providers behind one interface.

* HashingEmbedder — dependency-free, deterministic (signed feature hashing over word uni/bi-grams).
  Used for tests, CI and offline demos.
* SentenceTransformerEmbedder — BAAI/bge-small-en-v1.5 by default; production quality, runs on CPU.
* OpenAIEmbedder — text-embedding-3-small via API.
"""
from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

import numpy as np

from app.core.config import get_settings

_TOKEN = re.compile(r"[a-z0-9][a-z0-9.%$-]*")
_STOP = {"the", "a", "an", "of", "to", "and", "in", "is", "for", "on", "by", "with", "as", "be",
         "or", "at", "that", "this", "any", "its", "are", "was", "from", "it", "shall", "which"}


def tokenize(text: str) -> list[str]:
    return [t.strip(".") for t in _TOKEN.findall(text.lower()) if t not in _STOP]


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> np.ndarray: ...


class HashingEmbedder:
    def __init__(self, dim: int = 384):
        self.dim = dim

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        toks = tokenize(text)
        feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:], strict=False)]
        for f in feats:
            h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "little")
            idx, sign = h % self.dim, 1.0 if (h >> 63) & 1 else -1.0
            v[idx] += sign * (1.0 + math.log1p(len(f) / 8))
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.vstack([self._vec(t) for t in texts]) if texts else np.zeros((0, self.dim), np.float32)


class SentenceTransformerEmbedder:  # pragma: no cover - optional heavy dependency
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self.model.encode(texts, normalize_embeddings=True), dtype=np.float32)


class OpenAIEmbedder:  # pragma: no cover - network
    def __init__(self, model_name: str = "text-embedding-3-small"):
        from openai import OpenAI
        self.client, self.model, self.dim = OpenAI(), model_name, 1536

    def embed(self, texts: list[str]) -> np.ndarray:
        resp = self.client.embeddings.create(model=self.model, input=texts)
        arr = np.asarray([d.embedding for d in resp.data], dtype=np.float32)
        return arr / np.linalg.norm(arr, axis=1, keepdims=True)


@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    if s.embedding_provider == "sentence-transformers":
        return SentenceTransformerEmbedder(s.embedding_model)
    if s.embedding_provider == "openai":
        return OpenAIEmbedder()
    return HashingEmbedder(s.embedding_dim)
