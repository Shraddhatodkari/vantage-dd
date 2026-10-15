"""Retrieval resilience with a mocked network: retries, backoff, no retry on 4xx, snapshot integrity."""
import json

import httpx
import pytest
from app.core.config import get_settings
from app.sources import http as src


@pytest.fixture()
def tmp_snapshots(tmp_path, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "source_snapshot_dir", tmp_path)
    monkeypatch.setattr(s, "http_max_retries", 2)
    monkeypatch.setattr(src.time, "sleep", lambda *_: None)
    return tmp_path


def test_retries_then_succeeds_and_stores_snapshot(tmp_snapshots, monkeypatch):
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        if len(calls) < 3:
            return httpx.Response(503)
        return httpx.Response(200, content=b'{"ok": 1}')
    monkeypatch.setattr(src.httpx, "get", fake_get)
    r = src.fetch("https://example.org/x.json", "test", mode="live")
    assert len(calls) == 3 and r.json() == {"ok": 1} and r.mode == "live"
    m = json.loads((tmp_snapshots / "manifest.json").read_text(encoding="utf-8"))
    assert m["entries"]["https://example.org/x.json"][0]["sha256"] == r.sha256
    again = src.fetch("https://example.org/x.json", "test", mode="snapshot")
    assert again.content == r.content and again.mode == "snapshot"


def test_client_errors_are_not_retried(tmp_snapshots, monkeypatch):
    calls = []
    monkeypatch.setattr(src.httpx, "get", lambda url, **kw: calls.append(url) or httpx.Response(404))
    with pytest.raises(src.SourceUnavailable, match="404"):
        src.fetch("https://example.org/missing", "test", mode="live")
    assert len(calls) == 1


def test_timeouts_exhaust_bounded_retries(tmp_snapshots, monkeypatch):
    def boom(url, **kw):
        raise httpx.ConnectTimeout("timeout")
    monkeypatch.setattr(src.httpx, "get", boom)
    with pytest.raises(src.SourceUnavailable, match="after 3 attempts"):
        src.fetch("https://example.org/slow", "test", mode="live")


def test_tampered_snapshot_is_refused(tmp_snapshots, monkeypatch):
    monkeypatch.setattr(src.httpx, "get", lambda url, **kw: httpx.Response(200, content=b"original"))
    r = src.fetch("https://example.org/doc", "test", mode="live")
    r.local_path.write_bytes(b"tampered")
    with pytest.raises(src.SourceUnavailable, match="integrity"):
        src.fetch("https://example.org/doc", "test", mode="snapshot")


def test_missing_from_snapshot_is_an_explicit_error(tmp_snapshots):
    with pytest.raises(src.SourceUnavailable, match="not in the local source snapshot"):
        src.fetch("https://example.org/never", "test", mode="snapshot")
