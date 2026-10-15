# Optional container deployment (not required)

The supported path for this project is **native Windows / macOS / Linux without Docker** (see the main README and
`scripts/windows/`). These files are kept only for teams that deploy with containers. They are not part of the
verified test path and were not re-validated in the enterprise upgrade; review them before use
(in particular, set `VANTAGE_ENV=prod`, `VANTAGE_DEMO_MODE=false`, `VANTAGE_COOKIE_SECURE=true`).

Final release review (not executed — Docker is out of scope for this project's verified path): passwords now come
from `POSTGRES_PASSWORD` / `GRAFANA_ADMIN_PASSWORD` (compose refuses to start without them); auxiliary ports bind to
127.0.0.1; the unauthenticated MCP HTTP service was removed; Kubernetes runs exactly 1 replica with no autoscaler,
because the audit-chain lock is in-process; Render uses prod settings and the correct Dockerfile path; the image installs
the PostgreSQL driver.
