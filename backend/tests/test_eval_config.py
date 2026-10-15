"""The evaluation harness must find every golden case on any OS (it crashed on Windows: golden.json was read with
the cp1252 default, the em dash in the real-company names became mojibake, the lookup returned None and
create_run() failed on deal.id). These tests pin the fix and the no-substitution rule."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "ml" / "eval" / "golden.json"


def test_golden_case_names_resolve_to_seeded_deals(analyst):
    names = {d["name"]: d["data_classification"] for d in analyst.get("/api/v1/deals").json()}
    for case in json.loads(GOLDEN.read_text(encoding="utf-8"))["cases"]:
        if case.get("path"):
            assert (ROOT / case["path"]).is_dir(), case["path"]      # fixture created in the isolated eval DB
            continue
        assert case["name"] in names, case["name"]
        want = "verified_real" if case["kind"].startswith("verified_real") else "illustrative"
        assert names[case["name"]] == want, case["name"]


def test_golden_names_contain_non_ascii_and_would_break_without_utf8():
    raw = GOLDEN.read_bytes()
    utf8 = [c["name"] for c in json.loads(raw.decode("utf-8"))["cases"]]
    cp1252 = [c["name"] for c in json.loads(raw.decode("cp1252"))["cases"]]
    assert utf8 != cp1252                       # proves the regression is real, so explicit UTF-8 is required


def test_no_text_io_relies_on_the_platform_default_encoding():
    import re
    offenders = []
    for folder in ("backend/app", "backend/mcp_server", "scripts", "ml/eval"):
        for p in (ROOT / folder).rglob("*.py"):
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"\.read_text\(\)|\.open\(\"[wra]\"\)", line):
                    offenders.append(f"{p.relative_to(ROOT)}:{i}")
    assert offenders == []
