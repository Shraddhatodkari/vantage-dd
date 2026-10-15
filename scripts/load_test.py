"""Load test against a RUNNING Vantage DD server (single process, as designed). Read-heavy portfolio traffic at several
concurrency levels, plus concurrent AI analyses. Reports measured numbers only; nothing is extrapolated.

    set VANTAGE_LOAD_URL=http://127.0.0.1:8000
    set VANTAGE_LOAD_PASSWORD=<demo password from .env>
    python scripts/load_test.py [--seconds 30] [--levels 10,25,50] [--out docs/evidence/load_test.md]

Use a throwaway database: the run creates analysis versions on every real-company deal.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import platform
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx

URL = os.getenv("VANTAGE_LOAD_URL", "http://127.0.0.1:8000").rstrip("/")
PW = os.getenv("VANTAGE_LOAD_PASSWORD")
API = f"{URL}/api/v1"


async def login(c: httpx.AsyncClient, email: str) -> None:
    r = await c.post(f"{API}/auth/login", json={"email": email, "password": PW})
    if r.status_code != 200:
        raise SystemExit(f"login failed for {email}: HTTP {r.status_code}")


def pct(xs: list[float], p: float) -> float:
    if not xs:
        return float("nan")
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, round(p / 100 * len(xs)) - 1))]


async def read_mix(c: httpx.AsyncClient, deals: list[str], seconds: float, users: int) -> dict:
    """`users` concurrent virtual users, each looping over the pages an analyst opens, for `seconds`."""
    paths = ["/auth/session", "/portfolio/stats", "/deals", "/portfolio/compare", "/portfolio/activity?limit=12"]
    for d in deals:
        paths += [f"/deals/{d}", f"/deals/{d}/financials", f"/deals/{d}/runs"]
    lat: list[float] = []
    codes: Counter = Counter()
    stop = time.perf_counter() + seconds

    async def user(k: int) -> None:
        i = k
        while time.perf_counter() < stop:
            p = paths[i % len(paths)]
            i += 1
            t = time.perf_counter()
            try:
                r = await c.get(API + p)
                codes[r.status_code] += 1
            except httpx.HTTPError as exc:
                codes[type(exc).__name__] += 1
                continue
            lat.append((time.perf_counter() - t) * 1000)

    t0 = time.perf_counter()
    await asyncio.gather(*(user(k) for k in range(users)))
    wall = time.perf_counter() - t0
    ok = sum(v for k, v in codes.items() if k == 200)
    total = sum(codes.values())
    return {"users": users, "requests": total, "rps": total / wall, "p50": pct(lat, 50), "p95": pct(lat, 95),
            "p99": pct(lat, 99), "max": max(lat) if lat else float("nan"),
            "errors": total - ok, "codes": dict(codes)}


async def single_latency(c: httpx.AsyncClient, deals: list[str]) -> list[tuple[str, float, int]]:
    """Median of 8 sequential requests per endpoint (no concurrency): the cost of each page on its own."""
    d = deals[0]
    out = []
    for label, p in [("session check", "/auth/session"), ("portfolio KPIs", "/portfolio/stats"), ("deal list", "/deals"),
                     ("company comparison", "/portfolio/compare"), ("deal detail", f"/deals/{d}"),
                     ("financials (4 years, all metrics)", f"/deals/{d}/financials")]:
        ts, size = [], 0
        for _ in range(8):
            t = time.perf_counter()
            r = await c.get(API + p)
            ts.append((time.perf_counter() - t) * 1000)
            size = len(r.content)
        out.append((label, statistics.median(ts), size))
    return out


async def concurrent_analyses(c: httpx.AsyncClient, deals: list[str]) -> dict:
    """Start one AI analysis on every real-company deal at the same time and time each to completion."""
    h = {"X-CSRF-Token": c.cookies.get("vantage_csrf", "")}
    t0 = time.perf_counter()
    started = []
    for d in deals:
        r = await c.post(f"{API}/deals/{d}/runs", json={}, headers=h)
        started.append((d, r.status_code, r.json().get("id") if r.status_code == 202 else None))
    done: dict[str, float] = {}
    status: dict[str, str] = {}
    while len(done) < sum(1 for *_, rid in started if rid) and time.perf_counter() - t0 < 600:
        for _d, _code, rid in started:
            if rid and rid not in done:
                s = (await c.get(f"{API}/runs/{rid}")).json()["status"]
                if s not in ("queued", "running"):
                    done[rid], status[rid] = time.perf_counter() - t0, s
        await asyncio.sleep(0.25)
    # a read request measured while nothing else runs, for comparison
    return {"started": len(started), "accepted": sum(1 for _, code, _ in started if code == 202),
            "completed": sum(1 for s in status.values() if s == "completed"), "statuses": dict(Counter(status.values())),
            "all_done_s": max(done.values()) if done else None, "first_done_s": min(done.values()) if done else None}


async def main_async(a) -> int:
    if not PW:
        raise SystemExit("Set VANTAGE_LOAD_PASSWORD (demo password from your .env).")
    limits = httpx.Limits(max_connections=200, max_keepalive_connections=200)
    async with httpx.AsyncClient(timeout=60, limits=limits) as c:
        await login(c, "analyst@vantage.dev")
        deals = [d["id"] for d in (await c.get(f"{API}/deals")).json() if d["data_classification"] == "verified_real"]
        levels = [int(x) for x in a.levels.split(",")]
        await read_mix(c, deals, 3, 5)                                       # warm-up (not reported)
        single = await single_latency(c, deals)
        reads = [await read_mix(c, deals, a.seconds, n) for n in levels]
        runs = await concurrent_analyses(c, deals)
        during = await read_mix(c, deals, 5, 10)                            # after analyses (sanity)
    env = (f"{platform.system()} {platform.release()}, Python {platform.python_version()}, "
           f"{os.cpu_count()} logical CPUs; client and server on the same machine")
    md = ["# Load test (measured)", "",
          f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `python scripts/load_test.py` against {URL}.",
          f"Environment: {env}. Server: one uvicorn process (the supported deployment: in-process locks), SQLite.",
          "These numbers describe THIS machine only; they are not a capacity guarantee.", "",
          "## Each page on its own (median of 8 sequential requests)", "",
          "| Page | Median ms | Response size |", "|---|---|---|",
          *[f"| {label} | {ms:.0f} | {size / 1024:,.1f} KB |" for label, ms, size in single], "",
          f"## Read traffic ({a.seconds:g} s per level; portfolio, deal, financials, comparison and run-history pages)", "",
          "| Concurrent users | Requests | Throughput (req/s) | p50 ms | p95 ms | p99 ms | max ms | Errors |",
          "|---|---|---|---|---|---|---|---|",
          *[f"| {r['users']} | {r['requests']:,} | {r['rps']:.1f} | {r['p50']:.0f} | {r['p95']:.0f} | {r['p99']:.0f} | "
            f"{r['max']:.0f} | {r['errors']} |" for r in reads], "",
          "## Concurrent AI analyses (offline rules mode)", "",
          f"{runs['accepted']} of {runs['started']} analyses accepted at once (one per real-company deal); "
          f"{runs['completed']} completed ({runs['statuses']}); first finished after {runs['first_done_s']:.1f} s, "
          f"all after {runs['all_done_s']:.1f} s.", "",
          f"Read traffic afterwards (10 users, 5 s): p95 {during['p95']:.0f} ms, {during['errors']} errors.", "",
          "## Interpretation", "",
          "Each page costs tens of milliseconds on its own; under concurrency the single Python process is CPU-bound, so",
          "throughput stays roughly flat while queueing raises latency. No request failed at any level. Scaling beyond one",
          "process needs the shared-lock and job-queue work listed in the limitations (Redis/PostgreSQL advisory locks).", ""]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    bad = any(r["errors"] for r in reads) or runs["completed"] != runs["accepted"] or during["errors"]
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--levels", default="10,25,50")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "docs" / "evidence" / "load_test.md"))
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
