"""Vantage DD — FastAPI application entrypoint."""
from __future__ import annotations

import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import (  # noqa: E402
    FileResponse,
    JSONResponse,
    PlainTextResponse,
)
from fastapi.staticfiles import StaticFiles  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.api import routes_auth, routes_deals  # noqa: E402
from app.core.config import ROOT_DIR, get_settings, validate_settings  # noqa: E402
from app.core.logging import configure_logging, log, request_id_var  # noqa: E402
from app.db.seed import init_db, seed_demo  # noqa: E402
from app.db.session import engine  # noqa: E402

settings = get_settings()
_METRICS = {"requests_total": 0, "errors_total": 0, "latency_ms_sum": 0.0}


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    for w in validate_settings(settings):  # raises ConfigError on unsafe configuration
        log.warning(w)
    init_db(allow_upgrade=settings.auto_migrate)
    from app.agents.service import recover_interrupted_runs
    n = recover_interrupted_runs()
    if n:
        log.warning("marked %d interrupted run(s) as failed after restart", n)
    if settings.demo_mode:
        res = seed_demo()
        log.info("demo seed: %s", {k: v for k, v in res.items() if k != "real"})
    log.info("Vantage DD started (env=%s, demo_mode=%s, source_mode=%s)", settings.env, settings.demo_mode,
             settings.source_mode)
    yield


# production exposes neither interactive docs nor the machine-readable API schema
app = FastAPI(title=settings.app_name, version="1.2.0", lifespan=lifespan,
              docs_url=None if settings.env == "prod" else "/docs", redoc_url=None,
              openapi_url=None if settings.env == "prod" else "/openapi.json",
              description="Agentic due-diligence platform with verified real-source data, evidence-grounded "
                          "findings, partner approval and immutable reports.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type", "X-CSRF-Token", "Authorization"])


@app.middleware("http")
async def observability(request: Request, call_next):
    rid = uuid.uuid4().hex[:16]
    request_id_var.set(rid)
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:  # pragma: no cover - turned into a safe 500 below
        _METRICS["errors_total"] += 1
        log.exception("unhandled error on %s %s", request.method, request.url.path)  # path only: no query/body
        response = JSONResponse({"detail": "Internal error", "request_id": rid}, status_code=500)
    ms = (time.perf_counter() - t0) * 1000
    _METRICS["requests_total"] += 1
    _METRICS["latency_ms_sum"] += ms
    if response.status_code >= 500:
        _METRICS["errors_total"] += 1
    response.headers.update({
        "x-request-id": rid, "x-content-type-options": "nosniff", "x-frame-options": "DENY",
        "referrer-policy": "no-referrer", "cache-control": "no-store",
        # no 'unsafe-inline' anywhere: React applies inline styles through the DOM (CSSOM), which CSP permits
        "content-security-policy": "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
                                   "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
                                   "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
        "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=()",
    })
    if settings.cookie_secure:
        response.headers["strict-transport-security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    # never echo submitted values (could contain a password)
    return JSONResponse({"detail": [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]}, status_code=422)


app.include_router(routes_auth.router, prefix=settings.api_prefix)
app.include_router(routes_deals.router, prefix=settings.api_prefix)


@app.get("/healthz", tags=["ops"])
def healthz():
    return {"status": "ok"}


@app.get("/readyz", tags=["ops"])
def readyz():
    with engine.connect() as cx:
        cx.execute(text("SELECT 1"))
    return {"status": "ready", "env": settings.env, "source_mode": settings.source_mode,
            "llm_provider": settings.llm_provider}


@app.get("/metrics", response_class=PlainTextResponse, tags=["ops"])
def metrics(request: Request):
    if settings.env == "prod":
        # not public in production: a scraper must present VANTAGE_METRICS_TOKEN; without one the endpoint is off
        import hmac
        sent = request.headers.get("authorization", "")
        if not settings.metrics_token or not hmac.compare_digest(sent, f"Bearer {settings.metrics_token}"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
    return "\n".join([
        "# TYPE vantage_http_requests_total counter", f"vantage_http_requests_total {_METRICS['requests_total']}",
        "# TYPE vantage_http_errors_total counter", f"vantage_http_errors_total {_METRICS['errors_total']}",
        "# TYPE vantage_http_latency_ms_sum counter", f"vantage_http_latency_ms_sum {_METRICS['latency_ms_sum']:.1f}",
    ]) + "\n"


_DIST = ROOT_DIR / "frontend" / "dist"
CLIENT_ROUTE = re.compile(r"(?:login|reset-password|deals(?:/[A-Za-z0-9_-]+)?|compare|audit|account)?/?")
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        target = (_DIST / path).resolve()
        if path and target.is_file() and Path(target).is_relative_to(_DIST.resolve()):
            return FileResponse(target)
        # unknown API paths, dot-files and missing files are a plain 404
        last = path.rsplit("/", 1)[-1]
        if path.startswith(("api/", "api")) or any(seg.startswith(".") for seg in path.split("/")) or "." in last:
            return JSONResponse({"detail": "Not found"}, status_code=404)
        # the app's own client-side routes get the shell with 200; anything else gets it with 404 (the app then
        # redirects home), so scanners and caches never see a non-existent path as a real resource
        return FileResponse(_DIST / "index.html", status_code=200 if CLIENT_ROUTE.fullmatch(path) else 404)
