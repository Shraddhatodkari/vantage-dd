"""Resilient fetching of external sources with provenance.

* live mode: HTTP GET with timeout, bounded retries + exponential backoff (honours Retry-After),
  per-host rate limiting; the raw bytes are stored content-addressed in the snapshot directory and
  recorded in manifest.json (url -> list of retrievals). Existing snapshot files are never overwritten.
* snapshot mode: serves the most recent stored retrieval of that URL, with its original
  retrieval timestamp, so the UI can say exactly how old the data is. Nothing is fetched.
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings

log = logging.getLogger("vantage.sources")
RETRYABLE = {429, 500, 502, 503, 504}


class SourceUnavailable(RuntimeError):
    """The source could not be retrieved (network failure, HTTP error, or missing from the snapshot)."""


@dataclass
class Retrieved:
    url: str
    source: str
    content: bytes
    retrieved_at: datetime
    mode: str            # live | snapshot
    sha256: str
    local_path: Path

    def json(self):
        return json.loads(self.content)

    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


class _RateLimiter:
    def __init__(self):
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, host: str, per_second: float) -> None:
        with self._lock:
            gap = 1.0 / per_second
            now = time.monotonic()
            delay = self._last.get(host, 0) + gap - now
            if delay > 0:
                time.sleep(delay)
            self._last[host] = time.monotonic()


_limiter = _RateLimiter()
_manifest_lock = threading.Lock()


def _manifest_path() -> Path:
    return get_settings().source_snapshot_dir / "manifest.json"


def load_manifest() -> dict:
    p = _manifest_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"version": 1, "entries": {}}


def _save_manifest(m: dict) -> None:
    p = _manifest_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(m, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(p)  # atomic on Windows and POSIX


def _safe_name(url: str) -> str:
    u = urlparse(url)
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", (u.path.rsplit("/", 1)[-1] or "index") + ("_" + u.query if u.query else ""))
    return base[:80]


def fetch(url: str, source: str, *, headers: dict | None = None, mode: str | None = None) -> Retrieved:
    s = get_settings()
    mode = mode or s.source_mode
    if mode == "snapshot":
        return _from_snapshot(url, source)
    return _live(url, source, headers or {})


def _from_snapshot(url: str, source: str) -> Retrieved:
    entries = load_manifest()["entries"].get(url)
    if not entries:
        raise SourceUnavailable(f"{url} is not in the local source snapshot; refresh in live mode first")
    e = entries[-1]
    path = get_settings().source_snapshot_dir / e["path"]
    if not path.exists():
        raise SourceUnavailable(f"snapshot file missing for {url}: {e['path']}")
    content = path.read_bytes()
    sha = hashlib.sha256(content).hexdigest()
    if sha != e["sha256"]:
        raise SourceUnavailable(f"snapshot integrity check failed for {url} (sha256 mismatch)")
    return Retrieved(url, source, content, datetime.fromisoformat(e["retrieved_at"]), "snapshot", sha, path)


def _live(url: str, source: str, headers: dict) -> Retrieved:
    s = get_settings()
    host = urlparse(url).netloc
    ua = s.sec_user_agent or "Vantage DD (configure VANTAGE_SEC_USER_AGENT)"
    hdrs = {"User-Agent": ua, "Accept-Encoding": "gzip, deflate", **headers}
    per_second = s.sec_max_requests_per_second if host.endswith("sec.gov") else 4.0
    last_err: Exception | None = None
    for attempt in range(s.http_max_retries + 1):
        _limiter.wait(host, per_second)
        try:
            r = httpx.get(url, headers=hdrs, timeout=s.http_timeout_seconds, follow_redirects=True)
            if r.status_code == 200:
                return _store(url, source, r.content)
            if r.status_code not in RETRYABLE:
                raise SourceUnavailable(f"{url} returned HTTP {r.status_code}")
            retry_after = r.headers.get("Retry-After")
            last_err = SourceUnavailable(f"{url} returned HTTP {r.status_code}")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else 0.5 * 2 ** attempt
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_err = exc
            delay = 0.5 * 2 ** attempt
        if attempt < s.http_max_retries:
            time.sleep(min(delay, 10) + random.uniform(0, 0.25))  # nosec B311 - retry jitter, not security
    raise SourceUnavailable(f"{url} failed after {s.http_max_retries + 1} attempts: {last_err}")


def _store(url: str, source: str, content: bytes) -> Retrieved:
    s = get_settings()
    sha = hashlib.sha256(content).hexdigest()
    rel = Path(source) / f"{sha[:16]}_{_safe_name(url)}"
    path = s.source_snapshot_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():  # content-addressed: never overwrite
        path.write_bytes(content)
    now = datetime.now(timezone.utc)
    with _manifest_lock:
        m = load_manifest()
        lst = m["entries"].setdefault(url, [])
        if not lst or lst[-1]["sha256"] != sha:
            lst.append({"path": rel.as_posix(), "sha256": sha, "bytes": len(content), "source": source,
                        "retrieved_at": now.isoformat()})
        else:
            lst[-1]["last_verified_at"] = now.isoformat()  # same content re-retrieved
        _save_manifest(m)
    log.info("retrieved %s (%d bytes)", url, len(content))
    return Retrieved(url, source, content, now, "live", sha, path)
