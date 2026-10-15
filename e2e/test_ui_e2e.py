"""Browser end-to-end test of the full workflow against a RUNNING server (real data, real UI).

    # terminal 1: start the app in demo mode (see README)        # terminal 2:
    set VANTAGE_E2E_URL=http://127.0.0.1:8000                    pytest e2e -q
    set VANTAGE_E2E_PASSWORD=<demo password from .env>

Requires `pip install pytest-playwright` and `playwright install chromium` (or PLAYWRIGHT_CHROMIUM_PATH).
Screenshots are written to docs/screenshots/.
"""
import hashlib
import os
import re
from pathlib import Path

import pytest

URL = os.getenv("VANTAGE_E2E_URL")
PW = os.getenv("VANTAGE_E2E_PASSWORD")
SHOTS = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
pytestmark = pytest.mark.skipif(not (URL and PW), reason="set VANTAGE_E2E_URL and VANTAGE_E2E_PASSWORD")


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.getenv("PLAYWRIGHT_CHROMIUM_PATH") or None)
        yield b
        b.close()


def login(page, email):
    page.goto(f"{URL}/login")
    page.fill("#email", email)
    page.fill("#pw", PW)
    page.click("button:has-text('Sign in')")


def test_full_workflow(browser):
    SHOTS.mkdir(parents=True, exist_ok=True)
    errors = []
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.goto(f"{URL}/login")
    page.wait_for_selector("[data-testid=demo-accounts]")
    body = page.inner_text("body")
    assert PW not in body and "@".join(["Vantage", "2026"]) not in body   # the old fixed password, built so docs/code never contain it
    assert page.get_attribute("#pw", "type") == "password"
    page.fill("#pw", "typed-secret")
    page.click("button[aria-label='Show password']")
    assert page.get_attribute("#pw", "type") == "text"
    page.click("button[aria-label='Hide password']")
    page.fill("#pw", "")
    page.screenshot(path=str(SHOTS / "01-login.png"))

    # analyst: dashboard -> Yellow -> run
    login(page, "analyst@vantage.dev")
    page.wait_for_selector("text=Verified real-data portfolio")
    page.wait_for_timeout(800)
    page.screenshot(path=str(SHOTS / "02-portfolio-dashboard.png"), full_page=True)
    page.click("text=Yellow Corporation — FY2022 credit review >> nth=0")
    page.wait_for_selector("text=Historical case")
    page.click("button:has-text('Run AI diligence')")
    page.wait_for_selector("[data-testid=submit-panel]", timeout=90000)       # completed draft, not yet submitted
    assert "rules only" in page.inner_text("[data-testid=ai-mode]")             # AI mode disclosed
    assert page.locator("[data-testid=score-points]").count() >= 10
    page.wait_for_timeout(500)
    page.screenshot(path=str(SHOTS / "03-agent-analysis.png"))
    page.click("[data-testid='finding-FIN.MATURITY_WALL'] button:has-text('evidence')")
    page.wait_for_timeout(300)
    page.locator("[data-testid='finding-FIN.MATURITY_WALL']").screenshot(path=str(SHOTS / "04-evidence.png"))
    # financials tab: values equal to the 10-K
    page.click("role=tab[name=/Financials/]")
    page.wait_for_selector("[data-testid=financials-table]")
    assert page.inner_text("[data-testid=fact-revenue-2022]").startswith("$5,244.7M")
    assert page.inner_text("[data-testid=fact-free_cash_flow-2022]").startswith("-$70.5M")
    assert page.inner_text("[data-testid=fact-total_debt-2022]").startswith("$1,538.0M")
    page.wait_for_selector("[data-testid=chart-revenue] svg")
    page.click("[data-testid=fact-total_debt-2022]")
    assert "1,538.0" in page.inner_text("[data-testid=fact-passage]")           # the 10-K line itself
    assert page.get_attribute("[data-testid=filing-link]", "href").endswith("yell-20221231.htm")
    page.click("[data-testid=fact-free_cash_flow-2022]")
    page.screenshot(path=str(SHOTS / "05-financials-provenance.png"), full_page=True)
    page.click("role=tab[name=/Sources/]")
    page.wait_for_selector("text=529900SEX4UQ2WLPRC40")
    page.screenshot(path=str(SHOTS / "06-sources-identity.png"))
    # analyst submits the analysis for partner review
    page.click("role=tab[name=/Analysis/]")
    page.fill("textarea[aria-label='Submission note']", "Checked findings and coverage; market study missing.")
    page.click("button:has-text('Submit for partner review')")
    page.wait_for_selector("[data-testid=submission]")
    page.wait_for_selector("text=Awaiting partner sign-off")
    page.click("button:has-text('Sign out')")

    # partner approves -> memo; downloaded file must equal the displayed version
    login(page, "partner@vantage.dev")
    page.wait_for_selector("text=Verified real-data portfolio")
    page.click("text=Yellow Corporation — FY2022 credit review >> nth=0")
    page.fill("textarea[aria-label='Review note']", "Historical case reviewed; conditions noted.")
    page.click("button:has-text('Approve')")
    page.wait_for_selector("text=Partner decision")
    page.click("role=tab[name=/IC memo/]")
    page.wait_for_selector("[data-testid=memo]")
    shown_sha = page.inner_text("[data-testid=report-sha]").rstrip("…")
    with page.expect_download() as dl:
        page.click("a:has-text('Download .md')")
    content = Path(dl.value.path()).read_bytes()
    assert hashlib.sha256(content).hexdigest().startswith(shown_sha)
    assert b"VERIFIED REAL DATA" in content and b"0000950170-23-002332" in content
    for h in (b"## 1. Executive summary", b"## 2. Credit thesis", b"## 7. Evidence coverage", b"## 11. Approval history"):
        assert h in content
    assert b"Submitted for partner review | analyst@vantage.dev" in content
    with page.expect_download() as dl2:
        page.click("a:has-text('Download printable .html')")
    html = Path(dl2.value.path()).read_text(encoding="utf-8")
    assert "<table>" in html and "Executive summary" in html and "<script" not in html and shown_sha in html
    page.screenshot(path=str(SHOTS / "07-ic-memo.png"))
    page.click("button:has-text('Sign out')")

    # admin: governance view, no deal evidence
    login(page, "admin@vantage.dev")
    page.wait_for_selector("text=Administration")
    assert "rules only" in page.inner_text("[data-testid=ai-mode]")
    page.click("button:has-text('Run connectivity check')")
    page.wait_for_selector("text=No LLM provider configured")
    page.click("button:has-text('Verify chain')")
    page.wait_for_selector("text=Hash chain intact")
    page.screenshot(path=str(SHOTS / "08-admin-audit.png"))
    assert not re.search(r"Run AI diligence", page.inner_text("body"))
    assert not errors, errors


def test_old_dominion_rejection_coverage_and_history(browser):
    """Second real company: coverage disclosure, FCF rounding transparency, GLEIF mismatch not auto-accepted,
    snapshot labelling, rejection that requires a reason, and analysis history."""
    errors = []
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    login(page, "analyst@vantage.dev")
    page.wait_for_selector("text=Verified real-data portfolio")
    page.click("text=Old Dominion Freight Line — FY2022 credit review >> nth=0")
    page.wait_for_selector("text=Historical case")
    assert "2023" in page.inner_text("text=/filed on or before/")
    page.click("button:has-text('Run AI diligence')")
    page.wait_for_selector("[data-testid=coverage-panel]", timeout=90000)
    cov = page.inner_text("[data-testid=coverage-panel]")
    assert "Independent market or industry study" in cov and "insufficient evidence" in cov and "not a clean result" in cov
    assert "not a guarantee" in page.inner_text("[data-testid=score-disclaimer]")
    assert page.locator("[data-testid='finding-RED.COVERAGE_GAP.market_strategist']").count() == 1
    cash = page.inner_text("[data-testid='finding-FIN.CASH_DECLINE']")
    assert "net cash" in cash and "LOW" in cash.upper()
    page.screenshot(path=str(SHOTS / "09-odfl-coverage.png"), full_page=True)
    page.click("role=tab[name=/Financials/]")
    page.wait_for_selector("[data-testid=financials-table]")
    assert page.inner_text("[data-testid=fact-free_cash_flow-2022]").startswith("$916.4M")
    assert page.inner_text("[data-testid=fact-interest_expense-2022]").startswith("$1.6M")   # us-gaap:InterestAndDebtExpense
    page.click("[data-testid=fact-free_cash_flow-2022]")
    inputs = page.inner_text("[data-testid=calc-inputs]")
    assert "1,691.582" in inputs and "775.148" in inputs
    page.click("[data-testid=fact-capex-2022]")
    assert "matched" in page.inner_text("[data-testid=doc-check]") and "775,148" in page.inner_text("[data-testid=doc-check]")
    assert "Purchase of property and equipment (775,148" in page.inner_text("[data-testid=fact-passage]")
    assert page.inner_text("[data-testid=fact-interest_coverage_x-2022]").startswith("1,354x")   # no false precision
    page.screenshot(path=str(SHOTS / "10-odfl-fcf-provenance.png"))
    page.click("role=tab[name=/Sources/]")
    page.wait_for_selector("text=Not auto-accepted")
    assert "5299009TWK32WE417T96" in page.inner_text("body")       # shown as a candidate, not as the verified LEI
    assert "not verified" in page.inner_text("body")
    modes = page.locator("[data-testid=source-mode]").all_inner_texts()
    assert modes and all("Stored snapshot" in m or "Retrieved live" in m for m in modes)
    page.screenshot(path=str(SHOTS / "11-odfl-identity-sources.png"))
    page.click("role=tab[name=/Analysis/]")
    page.click("button:has-text('Submit for partner review')")
    page.wait_for_selector("text=Awaiting partner sign-off")
    page.click("button:has-text('Sign out')")

    # partner: rejection needs a reason
    login(page, "partner@vantage.dev")
    page.wait_for_selector("text=Verified real-data portfolio")
    page.click("text=Old Dominion Freight Line — FY2022 credit review >> nth=0")
    page.wait_for_selector("text=Partner review required")
    reject = page.get_by_role("button", name="Reject", exact=True)
    assert reject.is_disabled()
    page.fill("textarea[aria-label='Review note']", "Market workstream had no documents; add an industry study and re-run.")
    assert reject.is_enabled()
    reject.click()
    page.wait_for_selector("text=Partner decision")
    assert "rejected" in page.inner_text("text=Partner decision >> xpath=..")
    page.screenshot(path=str(SHOTS / "12-odfl-rejected.png"))
    page.click("button:has-text('Sign out')")

    # analyst sees the rejection and can re-run; history lists both versions
    login(page, "analyst@vantage.dev")
    page.wait_for_selector("text=Verified real-data portfolio")
    page.click("text=Old Dominion Freight Line — FY2022 credit review >> nth=0")
    page.wait_for_selector("text=Market workstream had no documents")
    page.click("button:has-text('Run AI diligence')")
    page.wait_for_selector("[data-testid=submit-panel]", timeout=90000)      # new version starts as a draft
    page.wait_for_selector("[data-testid=run-history]", timeout=30000)
    hist = page.inner_text("[data-testid=run-history]")
    assert "rejected" in hist and "completed" in hist
    page.screenshot(path=str(SHOTS / "13-odfl-history.png"))
    # revision -> resubmission -> independent approval of the NEW version -> memo of exactly that version
    page.fill("textarea[aria-label='Submission note']", "Re-run after rejection; market study still not available.")
    page.click("button:has-text('Submit for partner review')")
    page.wait_for_selector("text=Awaiting partner sign-off")
    page.click("button:has-text('Sign out')")
    login(page, "partner@vantage.dev")
    page.wait_for_selector("text=Verified real-data portfolio")
    page.click("text=Old Dominion Freight Line — FY2022 credit review >> nth=0")
    page.wait_for_selector("text=Partner review required")
    page.fill("textarea[aria-label='Review note']", "Approved v2 for the historical case study; market gap noted.")
    page.click("button:has-text('Approve')")
    page.wait_for_selector("text=Partner decision")
    assert "Latest analysis v2" in page.inner_text("[data-testid=version-state]") and "last approved v2" in page.inner_text("[data-testid=version-state]")
    page.click("role=tab[name=/IC memo/]")
    page.wait_for_selector("[data-testid=memo]")
    with page.expect_download() as dl:
        page.click("a:has-text('Download .md')")
    memo = Path(dl.value.path()).read_text(encoding="utf-8")
    assert "analysis version 2" in memo and "Re-run after rejection" in memo and "Approved v2 for the historical" in memo
    assert "gross leverage" in memo.lower() and "| Net leverage (net debt / EBITDA) |" in memo
    page.screenshot(path=str(SHOTS / "13b-odfl-v2-approved-memo.png"), full_page=True)
    page.click("button:has-text('Sign out')")
    # audit trail in the browser: actor, action, version, verified chain
    login(page, "admin@vantage.dev")
    page.wait_for_selector("text=Administration")
    page.fill("input[aria-label='Filter audit log']", "run_")
    page.wait_for_timeout(300)
    audit = page.inner_text("[data-testid=audit-table]")
    for action in ("run_started", "run_submitted", "run_rejected", "run_approved"):
        assert action in audit, action
    assert "analyst@vantage.dev" in audit and "partner@vantage.dev" in audit and '"version":2' in audit
    page.click("button:has-text('Verify chain')")
    page.wait_for_selector("text=Hash chain intact")
    page.screenshot(path=str(SHOTS / "13c-audit-trail.png"))
    assert not errors, errors


def test_dashboard_compare_and_no_secrets(browser):
    """Portfolio KPIs come from stored data, comparison matches deal financials, no password is ever displayed."""
    errors = []
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    login(page, "partner@vantage.dev")
    page.wait_for_selector("[data-testid=kpis-real]")
    k = page.inner_text("[data-testid=kpis-real]")
    # 5 companies: 236 reported values, 232 printed as such, 4 sums of separately printed lines (Diebold total debt)
    assert "FACTS CONFIRMED IN FILINGS" in k.upper() and "232 / 236" in k and "4 more are sums of separately printed lines" in k
    page.wait_for_selector("[data-testid=activity]")
    assert "submitted for review" in page.inner_text("[data-testid=activity]")
    assert PW not in page.content()
    page.screenshot(path=str(SHOTS / "14-portfolio-overview.png"), full_page=True)
    page.click("[data-testid=open-compare]")
    page.wait_for_selector("[data-testid=compare-table]")
    t = page.inner_text("[data-testid=compare-table]")
    for v in ("$6,260.1M", "$5,244.7M", "$916.4M", "-$70.5M", "3.82x", "2.09x", "1,354x"):
        assert v in t, v
    assert "not guarantees" in page.inner_text("[data-testid=compare]")
    page.wait_for_selector("[data-testid=cmp-revenue] svg")
    page.wait_for_timeout(400)
    page.screenshot(path=str(SHOTS / "15-company-comparison.png"), full_page=True)
    # latest version vs last approved version: re-run Yellow (approved v1) -> v2 draft; the approved memo stays visible
    page.goto(f"{URL}/")
    page.click("text=Yellow Corporation — FY2022 credit review >> nth=0")
    page.click("button:has-text('Run AI diligence')")
    page.wait_for_selector("[data-testid=submit-panel]", timeout=90000)
    state = page.inner_text("[data-testid=version-state]")
    assert "Latest analysis v2" in state and "last approved v1" in state, state
    page.click("role=tab[name=/IC memo/]")
    page.wait_for_selector("[data-testid=older-memo-note]")
    assert "approved memo for analysis v1" in page.inner_text("[data-testid=older-memo-note]")
    page.goto(f"{URL}/")
    page.wait_for_selector("[data-testid=kpis-real]")
    assert "approved v1" in page.inner_text("table")
    page.screenshot(path=str(SHOTS / "16-latest-vs-approved.png"), full_page=True)
    for path in ("/", "/compare", "/deals"):
        page.goto(f"{URL}{path}")
        page.wait_for_timeout(600)
        assert PW not in page.content()
    assert not errors, errors


# ---------------------------------------------------------------------------------------- 2FA and password reset
def _totp(secret: str, step: int) -> str:
    """RFC 6238 code, computed independently of the app (HMAC-SHA1, 6 digits)."""
    import base64
    import hmac
    import struct
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    mac = hmac.new(key, struct.pack(">Q", step), "sha1").digest()
    o = mac[-1] & 0x0F
    return str((struct.unpack(">I", mac[o:o + 4])[0] & 0x7FFFFFFF) % 1_000_000).zfill(6)


def _fresh_code(secret: str, used: list[int]) -> str:
    """A code for a time step not used before (the server refuses replays); waits at most one 30-second step."""
    import time
    target = (max(used) + 1) if used else int(time.time() // 30)
    while target > int(time.time() // 30) + 1:
        time.sleep(1)
    used.append(target)
    return _totp(secret, target)


def test_two_factor_sign_in_and_admin_password_reset(browser):
    import secrets
    email = f"e2e-{secrets.token_hex(4)}@vantage.dev"
    first_pw, new_pw = f"First-{secrets.token_hex(4)}!A1", f"Reset-{secrets.token_hex(4)}!B2"
    errors = []
    # admin creates a user (API, same cookies + CSRF as the browser)
    actx = browser.new_context(viewport={"width": 1440, "height": 900})
    admin = actx.new_page()
    admin.on("console", lambda m: m.type == "error" and errors.append(m.text))
    login(admin, "admin@vantage.dev")
    admin.wait_for_selector("[data-testid=users-table]")
    csrf = next(c["value"] for c in actx.cookies() if c["name"] == "vantage_csrf")
    r = actx.request.post(f"{URL}/api/v1/admin/users", headers={"X-CSRF-Token": csrf},
                          data={"email": email, "full_name": "E2E Analyst", "role": "analyst", "password": first_pw})
    assert r.status == 201, r.text()

    # the user enrols 2FA in the UI
    uctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = uctx.new_page()
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.goto(f"{URL}/login")
    page.fill("#email", email)
    page.fill("#pw", first_pw)
    page.click("button:has-text('Sign in')")
    page.wait_for_selector("text=Portfolio overview")
    page.click("text=Account security")
    page.click("button:has-text('Set up two-factor authentication')")
    page.wait_for_selector("[data-testid=mfa-setup] img[alt^='QR code']")
    secret = page.inner_text("[data-testid=mfa-secret]").replace(" ", "")
    page.screenshot(path=str(SHOTS / "17-account-2fa-setup.png"))
    used: list[int] = []
    page.fill("#mfa-code", _fresh_code(secret, used))
    page.click("button:has-text('Confirm and turn on')")
    page.wait_for_selector("[data-testid=mfa-status]:has-text('On')")
    page.click("text=Sign out")

    # sign-in now needs password + code; a wrong code is refused
    page.fill("#email", email)
    page.fill("#pw", first_pw)
    page.click("button:has-text('Sign in')")
    page.wait_for_selector("[data-testid=mfa-step]")
    assert not any(c["name"] == "vantage_access" for c in uctx.cookies())        # no session after the password alone
    good = _fresh_code(secret, used)
    page.fill("#code", "000000" if good != "000000" else "111111")
    page.click("button:has-text('Verify and sign in')")
    page.wait_for_selector("[role=alert]:has-text('Invalid or expired code')")
    page.screenshot(path=str(SHOTS / "18-sign-in-code-step.png"))
    page.fill("#code", good)
    page.click("button:has-text('Verify and sign in')")
    page.wait_for_selector("text=Portfolio overview")

    # admin issues a one-time reset link in the UI (two clicks, no dialog)
    admin.reload()
    row = admin.locator(f"tr[data-email='{email}']")
    row.locator("button:has-text('Reset password')").click()
    row.locator("button:has-text('Confirm: issue reset link')").click()
    admin.wait_for_selector("[data-testid=reset-link]")
    link = admin.input_value("[data-testid=reset-link] input")
    assert "/reset-password#token=" in link
    admin.screenshot(path=str(SHOTS / "19-admin-users-reset-link.png"))

    # the user opens the link (in a fresh browser), sets a new password; the old session is signed out
    rctx = browser.new_context(viewport={"width": 1440, "height": 900})
    rp = rctx.new_page()
    rp.goto(link)
    rp.wait_for_selector("[data-testid=reset-password]")
    assert "#token=" not in rp.url                                                # removed from the address bar
    rp.fill("#new-pw", new_pw)
    rp.fill("#new-pw2", new_pw)
    rp.click("button:has-text('Set password')")
    rp.wait_for_selector("text=Password set")
    rp2 = rctx.new_page()                                                         # the link works once
    rp2.goto(link)
    rp2.fill("#new-pw", new_pw + "x")
    rp2.fill("#new-pw2", new_pw + "x")
    rp2.click("button:has-text('Set password')")
    rp2.wait_for_selector("[role=alert]:has-text('invalid, already used or expired')")
    page.goto(f"{URL}/deals")
    page.wait_for_url("**/login")                                                 # old session no longer valid

    # sign in with the new password + a fresh code
    page.fill("#email", email)
    page.fill("#pw", new_pw)
    page.click("button:has-text('Sign in')")
    page.wait_for_selector("[data-testid=mfa-step]")
    page.fill("#code", _fresh_code(secret, used))
    page.click("button:has-text('Verify and sign in')")
    page.wait_for_selector("text=Portfolio overview")

    # audit trail shows every step, and never the secret or the reset token
    admin.goto(f"{URL}/audit")
    admin.wait_for_selector("[data-testid=audit-table]")
    admin.fill("input[aria-label='Filter audit log']", "")
    text = admin.inner_text("body")
    for a in ("mfa_enabled", "login_mfa_failed", "login_password_ok_mfa_pending", "password_reset_issued",
              "password_reset_completed", "password_reset_invalid"):
        assert a in text, a
    token = link.split("token=")[1]
    assert secret not in admin.content() and token not in admin.content()
    admin.click("button:has-text('Verify chain')")
    admin.wait_for_selector("text=Hash chain intact")
    for c in (actx, uctx, rctx):
        c.close()
    assert not [e for e in errors if "401" not in e and "Unauthorized" not in e], errors
