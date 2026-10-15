# Load test (measured)

Generated 2026-10-14 13:57 UTC by `python scripts/load_test.py` against http://127.0.0.1:8790.
Environment: Linux 6.18.44-fc-v114, Python 3.13.16, 2 logical CPUs; client and server on the same machine. Server: one uvicorn process (the supported deployment: in-process locks), SQLite.
These numbers describe THIS machine only; they are not a capacity guarantee.

## Each page on its own (median of 8 sequential requests)

| Page | Median ms | Response size |
|---|---|---|
| session check | 8 | 0.4 KB |
| portfolio KPIs | 43 | 4.4 KB |
| deal list | 13 | 5.0 KB |
| company comparison | 54 | 44.3 KB |
| deal detail | 17 | 8.6 KB |
| financials (4 years, all metrics) | 25 | 108.3 KB |

## Read traffic (30 s per level; portfolio, deal, financials, comparison and run-history pages)

| Concurrent users | Requests | Throughput (req/s) | p50 ms | p95 ms | p99 ms | max ms | Errors |
|---|---|---|---|---|---|---|---|
| 10 | 1,257 | 41.6 | 167 | 763 | 1064 | 1336 | 0 |
| 25 | 1,131 | 37.3 | 549 | 1632 | 2438 | 3568 | 0 |
| 50 | 1,245 | 40.0 | 1193 | 2194 | 2849 | 4002 | 0 |

## Concurrent AI analyses (offline rules mode)

5 of 5 analyses accepted at once (one per real-company deal); 5 completed ({'completed': 5}); first finished after 2.3 s, all after 3.0 s.

Read traffic afterwards (10 users, 5 s): p95 922 ms, 0 errors.

## Interpretation

Each page costs tens of milliseconds on its own; under concurrency the single Python process is CPU-bound, so
throughput stays roughly flat while queueing raises latency. No request failed at any level. Scaling beyond one
process needs the shared-lock and job-queue work listed in the limitations (Redis/PostgreSQL advisory locks).
