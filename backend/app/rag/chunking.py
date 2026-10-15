"""Structure-aware chunking: paragraph/section boundaries first, then a sliding window with overlap.

CSV financial statements are converted to one self-describing sentence per row so that numeric
facts survive retrieval with their column labels attached (a common failure mode of naive RAG).
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    filename: str
    doc_type: str
    text: str
    position: int
    metadata: dict = field(default_factory=dict)


_SECTION_RE = re.compile(r"\n(?=(?:Section|Contract|\d+\.)\s)")


def _split_paragraphs(text: str) -> list[str]:
    parts: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        parts.extend(p.strip() for p in _SECTION_RE.split(block) if p.strip())
    return parts


def _window(text: str, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text]
    out, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        # prefer to break on a sentence boundary
        cut = text.rfind(". ", start + size // 2, end)
        if cut != -1 and end < len(text):
            end = cut + 1
        out.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return out


def csv_to_sentences(text: str, entity: str = "The company") -> list[str]:
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        year = row.pop("fiscal_year", "?")
        facts = ", ".join(f"{k.replace('_musd', ' ($M)').replace('_', ' ')} = {v}" for k, v in row.items())
        rows.append(f"{entity} FY{year} financials: {facts}.")
    return rows


def chunk_document(doc_id: str, filename: str, doc_type: str, text: str,
                   size: int = 700, overlap: int = 120) -> list[Chunk]:
    if filename.lower().endswith(".csv"):
        pieces = csv_to_sentences(text)
    else:
        pieces = []
        buf = ""
        for para in _split_paragraphs(text):
            if len(buf) + len(para) + 1 <= size:
                buf = f"{buf}\n{para}".strip()
            else:
                if buf:
                    pieces.extend(_window(buf, size, overlap))
                buf = para
        if buf:
            pieces.extend(_window(buf, size, overlap))
    return [
        Chunk(chunk_id=f"{doc_id}:{i}", doc_id=doc_id, filename=filename, doc_type=doc_type,
              text=p, position=i)
        for i, p in enumerate(pieces)
    ]
