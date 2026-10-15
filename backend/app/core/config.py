"""Central configuration. Every setting can be overridden through environment variables or a `.env`
file (prefix VANTAGE_). `validate_settings()` runs at startup and refuses unsafe production configs."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]
INSECURE_DEFAULT_SECRET = "dev-only-insecure-secret-change-me-0000000000"  # nosec B105 - deliberately unusable: refused outside dev by validate_settings


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT_DIR / ".env", ".env"), env_prefix="VANTAGE_", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    # Demo mode seeds shared demo accounts and illustrative deals. It must be enabled explicitly and is
    # refused in production.
    demo_mode: bool = False
    app_name: str = "Vantage DD"
    api_prefix: str = "/api/v1"

    # ---- security
    jwt_secret: str = INSECURE_DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 1
    cookie_secure: bool = False            # must be True in prod (HTTPS); enforced by validate_settings
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    login_rate_limit_per_minute: int = 10
    max_failed_logins: int = 5
    min_password_length: int = 12
    seed_password: str | None = None       # demo accounts' password; required when demo_mode is on
    # two-factor authentication (authenticator-app codes) and password reset
    mfa_issuer: str = "Vantage DD"
    mfa_encryption_key: str | None = None  # Fernet key for TOTP secrets; derived from jwt_secret when unset
    mfa_required_roles: list[str] = []     # e.g. ["admin","partner"]: these roles must enrol before using the app
    mfa_login_minutes: int = 5             # time allowed between the password step and the code step
    password_reset_minutes: int = 30       # lifetime of an administrator-issued reset link
    metrics_token: str | None = None       # prod: /metrics requires "Authorization: Bearer <token>" (404 if unset)

    # ---- storage
    database_url: str = f"sqlite:///{ROOT_DIR / 'backend' / 'vantage.db'}"
    checkpoint_db: Path = ROOT_DIR / "backend" / "checkpoints.db"
    vector_backend: Literal["memory", "pgvector"] = "memory"
    vector_index_dir: Path = ROOT_DIR / "backend" / ".vector_index"
    storage_dir: Path = ROOT_DIR / "backend" / ".storage"
    backup_dir: Path = ROOT_DIR / "backups"
    sample_data_dir: Path = ROOT_DIR / "data" / "sample_deals"
    max_upload_mb: int = 20
    auto_migrate: bool = False             # start-up never upgrades an existing DB unless explicitly enabled

    # ---- external sources
    # snapshot: use the source snapshots committed in data/source_snapshots (retrieved earlier, labelled with
    # their retrieval time). live: fetch from SEC / GLEIF / FRED and store a new snapshot.
    source_mode: Literal["snapshot", "live"] = "snapshot"
    source_snapshot_dir: Path = ROOT_DIR / "data" / "source_snapshots"
    sec_user_agent: str | None = None      # SEC requires "Name email" — mandatory for live SEC access
    http_timeout_seconds: float = 20.0
    http_max_retries: int = 3
    sec_max_requests_per_second: float = 8.0  # SEC fair-access limit is 10/s
    source_stale_after_days: int = 30

    # ---- LLM ("offline" = deterministic tools + rules only, no API key needed)
    llm_provider: Literal["offline", "anthropic", "openai"] = "offline"
    llm_model: str = "claude-sonnet-4-5"
    llm_temperature: float = 0.0
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None

    # ---- embeddings / retrieval
    embedding_provider: Literal["hashing", "sentence-transformers", "openai"] = "hashing"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    chunk_size: int = 700
    chunk_overlap: int = 120
    top_k: int = 6
    hybrid_alpha: float = 0.55

    # ---- MLOps
    mlflow_tracking_uri: str = f"sqlite:///{ROOT_DIR / 'mlflow.db'}"
    mlflow_experiment: str = "vantage-dd-agents"
    mlflow_enabled: bool = True

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


class ConfigError(RuntimeError):
    pass


_PLACEHOLDER = ("replace_with", "replace-with", "change_me", "changeme", "change-me", "placeholder", "your_", "your-")


def looks_like_placeholder(value: str | None) -> bool:
    v = (value or "").strip().lower()
    return bool(v) and (any(p in v for p in _PLACEHOLDER) or v.startswith(("<", "#")))


def validate_settings(s: Settings) -> list[str]:
    """Return warnings; raise ConfigError for configurations that must never run."""
    errors, warnings = [], []
    if s.env == "prod":
        if s.jwt_secret == INSECURE_DEFAULT_SECRET or len(s.jwt_secret) < 32:
            errors.append("VANTAGE_JWT_SECRET must be set to a random value of at least 32 characters in prod")
        if s.demo_mode:
            errors.append("VANTAGE_DEMO_MODE must be false in prod (demo accounts use shared credentials)")
        if not s.cookie_secure:
            errors.append("VANTAGE_COOKIE_SECURE must be true in prod (cookies only over HTTPS)")
        if any(o.startswith("http://") and "localhost" not in o for o in s.cors_origins):
            errors.append("VANTAGE_CORS_ORIGINS must use https origins in prod")
    else:
        if not s.jwt_secret.strip():
            errors.append("VANTAGE_JWT_SECRET is empty; run `python scripts/manage.py setup` or set a random value")
        elif s.jwt_secret == INSECURE_DEFAULT_SECRET:
            warnings.append("Using the built-in development JWT secret. Run `python scripts/manage.py setup` "
                            "to generate a .env with a random secret.")
    if s.demo_mode and not s.seed_password:
        errors.append("VANTAGE_SEED_PASSWORD is required when VANTAGE_DEMO_MODE=true "
                      "(run `python scripts/manage.py setup`)")
    # template / placeholder text copied from documentation is public: never accept it as a secret
    if looks_like_placeholder(s.jwt_secret):
        errors.append("VANTAGE_JWT_SECRET contains placeholder text; run `python scripts/manage.py setup` or set a "
                      "random value")
    if s.demo_mode and s.seed_password:
        if looks_like_placeholder(s.seed_password):
            errors.append("VANTAGE_SEED_PASSWORD contains placeholder text; run `python scripts/manage.py setup`")
        import re
        pw = s.seed_password
        if len(pw) < s.min_password_length or not (re.search(r"[A-Z]", pw) and re.search(r"[a-z]", pw)
                                                   and re.search(r"\d", pw) and re.search(r"[^A-Za-z0-9]", pw)):
            errors.append(f"VANTAGE_SEED_PASSWORD must be at least {s.min_password_length} characters with upper- and "
                          "lower-case letters, a digit and a symbol (run `python scripts/manage.py setup`)")
    if s.source_mode == "live" and not s.sec_user_agent:
        errors.append('VANTAGE_SEC_USER_AGENT ("Your Name your@email") is required for live SEC access')
    if errors:
        raise ConfigError("; ".join(errors))
    return warnings


@lru_cache
def get_settings() -> Settings:
    return Settings()
