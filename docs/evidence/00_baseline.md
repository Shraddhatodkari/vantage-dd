# Baseline (before enterprise upgrade)

Recorded 2026-10-13T13:54Z on git tag `baseline-v1` (commit 9b150ca).

| Check | Command | Result |
|---|---|---|
| Backend tests | `cd backend && python -m pytest -q` | 26 passed, 0 failed, 0 skipped |
| Agent eval gate | `python ml/eval/run_eval.py` | PASSED (recall 1.0, groundedness 1.0, clean critical FP 0) |
| Frontend type-check | `cd frontend && npx tsc -b --noEmit` | passed |
