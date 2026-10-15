"""FRED (Federal Reserve Bank of St. Louis) series via the public fredgraph CSV endpoint (no API key)."""
from __future__ import annotations

import csv
import io
from datetime import date

from app.sources.http import Retrieved, SourceUnavailable, fetch

CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
SERIES_PAGE = "https://fred.stlouisfed.org/series/{series}"
SERIES = {"FEDFUNDS": "Effective Federal Funds Rate, monthly average, percent"}


def get_series(series_id: str, mode: str | None = None) -> tuple[list[tuple[date, float | None]], Retrieved]:
    r = fetch(CSV_URL.format(series=series_id), "fred", mode=mode)
    rows = list(csv.reader(io.StringIO(r.text())))
    if not rows or len(rows[0]) < 2 or rows[0][1] != series_id:
        raise SourceUnavailable(f"Unexpected FRED CSV header for {series_id}: {rows[0] if rows else 'empty'}")
    out = []
    for d, v in rows[1:]:
        try:
            out.append((date.fromisoformat(d), None if v in ("", ".") else float(v)))
        except ValueError as exc:
            raise SourceUnavailable(f"Malformed FRED row {d},{v}") from exc
    return out, r
