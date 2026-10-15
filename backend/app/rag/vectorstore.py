"""Vector store abstraction, namespaced per deal (tenant isolation: one deal can never retrieve
another deal's documents — important for consulting confidentiality / ethical walls).

* LocalVectorStore — numpy matrix persisted to disk; zero infra.
* PgVectorStore    — Postgres + pgvector (HNSW index) for production; selected with
                     VANTAGE_VECTOR_BACKEND=pgvector.
"""
from __future__ import annotations

import json
import threading
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import numpy as np

from app.core.config import get_settings
from app.rag.chunking import Chunk


class VectorStore(Protocol):
    def add(self, namespace: str, chunks: list[Chunk], vectors: np.ndarray) -> None: ...
    def search(self, namespace: str, query_vec: np.ndarray, k: int) -> list[tuple[Chunk, float]]: ...
    def all_chunks(self, namespace: str) -> list[Chunk]: ...
    def delete_doc(self, namespace: str, doc_id: str) -> None: ...


class LocalVectorStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, tuple[list[Chunk], np.ndarray]] = {}
        self._lock = threading.Lock()

    def _paths(self, ns: str) -> tuple[Path, Path]:
        safe = "".join(c for c in ns if c.isalnum() or c in "-_")
        return self.root / f"{safe}.json", self.root / f"{safe}.npy"

    def _load(self, ns: str) -> tuple[list[Chunk], np.ndarray]:
        if ns in self._cache:
            return self._cache[ns]
        meta_p, vec_p = self._paths(ns)
        if meta_p.exists() and vec_p.exists():
            chunks = [Chunk(**c) for c in json.loads(meta_p.read_text(encoding="utf-8"))]
            vecs = np.load(vec_p)
        else:
            chunks, vecs = [], np.zeros((0, 0), dtype=np.float32)
        self._cache[ns] = (chunks, vecs)
        return chunks, vecs

    def _save(self, ns: str, chunks: list[Chunk], vecs: np.ndarray) -> None:
        meta_p, vec_p = self._paths(ns)
        meta_p.write_text(json.dumps([asdict(c) for c in chunks]), encoding="utf-8")
        np.save(vec_p, vecs)
        self._cache[ns] = (chunks, vecs)

    def add(self, namespace: str, chunks: list[Chunk], vectors: np.ndarray) -> None:
        with self._lock:
            old_c, old_v = self._load(namespace)
            vecs = vectors if old_v.size == 0 else np.vstack([old_v, vectors])
            self._save(namespace, old_c + chunks, vecs.astype(np.float32))

    def search(self, namespace: str, query_vec: np.ndarray, k: int) -> list[tuple[Chunk, float]]:
        chunks, vecs = self._load(namespace)
        if not chunks:
            return []
        scores = vecs @ query_vec
        idx = np.argsort(-scores)[:k]
        return [(chunks[i], float(scores[i])) for i in idx]

    def all_chunks(self, namespace: str) -> list[Chunk]:
        return list(self._load(namespace)[0])

    def delete_doc(self, namespace: str, doc_id: str) -> None:
        with self._lock:
            chunks, vecs = self._load(namespace)
            keep = [i for i, c in enumerate(chunks) if c.doc_id != doc_id]
            self._save(namespace, [chunks[i] for i in keep], vecs[keep] if keep else np.zeros((0, 0), np.float32))


class PgVectorStore:  # pragma: no cover - exercised in docker-compose integration env
    """Requires `CREATE EXTENSION vector;` (done by infra/postgres-init.sql)."""

    def __init__(self, url: str, dim: int):
        from sqlalchemy import create_engine, text
        self.text = text
        self.engine = create_engine(url, pool_pre_ping=True)
        self.dim = dim
        with self.engine.begin() as cx:
            cx.execute(text(f"""
                CREATE TABLE IF NOT EXISTS chunk_vectors (
                    chunk_id TEXT PRIMARY KEY, namespace TEXT NOT NULL, doc_id TEXT NOT NULL,
                    filename TEXT, doc_type TEXT, position INT, text TEXT, embedding vector({dim}))"""))
            cx.execute(text("CREATE INDEX IF NOT EXISTS ix_cv_ns ON chunk_vectors(namespace)"))
            cx.execute(text("CREATE INDEX IF NOT EXISTS ix_cv_hnsw ON chunk_vectors "
                            "USING hnsw (embedding vector_cosine_ops)"))

    @staticmethod
    def _lit(v: np.ndarray) -> str:
        return "[" + ",".join(f"{x:.6f}" for x in v.tolist()) + "]"

    def add(self, namespace, chunks, vectors):
        with self.engine.begin() as cx:
            for c, v in zip(chunks, vectors, strict=True):
                cx.execute(self.text(
                    "INSERT INTO chunk_vectors VALUES (:id,:ns,:doc,:fn,:dt,:pos,:tx,CAST(:emb AS vector)) "
                    "ON CONFLICT (chunk_id) DO NOTHING"),
                    dict(id=c.chunk_id, ns=namespace, doc=c.doc_id, fn=c.filename, dt=c.doc_type,
                         pos=c.position, tx=c.text, emb=self._lit(v)))

    def search(self, namespace, query_vec, k):
        with self.engine.connect() as cx:
            rows = cx.execute(self.text(
                "SELECT chunk_id, doc_id, filename, doc_type, position, text, "
                "1 - (embedding <=> CAST(:q AS vector)) AS score FROM chunk_vectors "
                "WHERE namespace=:ns ORDER BY embedding <=> CAST(:q AS vector) LIMIT :k"),
                dict(q=self._lit(query_vec), ns=namespace, k=k)).all()
        return [(Chunk(r[0], r[1], r[2], r[3], r[5], r[4]), float(r[6])) for r in rows]

    def all_chunks(self, namespace):
        with self.engine.connect() as cx:
            rows = cx.execute(self.text(
                "SELECT chunk_id, doc_id, filename, doc_type, position, text FROM chunk_vectors "
                "WHERE namespace=:ns ORDER BY doc_id, position"), dict(ns=namespace)).all()
        return [Chunk(r[0], r[1], r[2], r[3], r[5], r[4]) for r in rows]

    def delete_doc(self, namespace, doc_id):
        with self.engine.begin() as cx:
            cx.execute(self.text("DELETE FROM chunk_vectors WHERE namespace=:ns AND doc_id=:d"),
                       dict(ns=namespace, d=doc_id))


@lru_cache
def get_vector_store() -> VectorStore:
    s = get_settings()
    if s.vector_backend == "pgvector":
        from app.rag.embeddings import get_embedder
        return PgVectorStore(s.database_url, get_embedder().dim)
    return LocalVectorStore(s.vector_index_dir)
