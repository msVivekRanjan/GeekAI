"""Application settings loaded from environment variables.

Stage S1 removes the seed-admin defaults and the usable database/JWT
placeholders. Every placeholder below is intentionally unusable in
production; real values must come from the environment or a secrets vault.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database — placeholder is intentionally unusable.
    DATABASE_URL: str = "postgresql+asyncpg://<user>:<password>@localhost:5432/geekai"
    # Optional direct (non-pooled) URL used by Alembic migrations against Neon.
    MIGRATION_DATABASE_URL: str = ""
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5

    @staticmethod
    def _normalize_async_url(raw_url: str) -> str:
        url = raw_url.strip()
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        parsed = urlparse(url)
        if parsed.query:
            qs = parse_qs(parsed.query, keep_blank_values=True)
            qs.pop("sslmode", None)
            qs.pop("channel_binding", None)
            new_query = urlencode(qs, doseq=True)
            url = urlunparse(parsed._replace(query=new_query))
        return url

    @property
    def async_database_url(self) -> str:
        """Normalize DATABASE_URL for asyncpg, stripping libpq-only query params."""
        return self._normalize_async_url(self.DATABASE_URL)

    @property
    def migration_database_url(self) -> str:
        """Use MIGRATION_DATABASE_URL (Neon direct) if set, else DATABASE_URL."""
        return self._normalize_async_url(self.MIGRATION_DATABASE_URL or self.DATABASE_URL)

    @property
    def async_connect_args(self) -> Dict[str, Any]:
        """Pass SSL context to asyncpg when connecting to Neon or sslmode=require."""
        raw = (self.MIGRATION_DATABASE_URL or self.DATABASE_URL).lower()
        if "sslmode=require" in raw or "neon.tech" in raw:
            return {"ssl": "require"}
        return {}

    @property
    def is_serverless_db(self) -> bool:
        """True only when running in serverless functions (Vercel) or USE_NULL_POOL=true."""
        return bool(os.getenv("VERCEL")) or os.getenv("USE_NULL_POOL", "").lower() == "true"

    # JWT — placeholder is intentionally unusable. Generate a real secret and
    # supply it via the environment or a secrets manager.
    SECRET_KEY: str = "<generate-a-random-value>"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # One-time bootstrap token for creating the first admin user. Must be set
    # in the environment before the first boot; there is no usable default.
    BOOTSTRAP_TOKEN: str = "<set-BOOTSTRAP_TOKEN-in-the-environment>"

    # Active event code used for JWT `event_ids` scope checks.
    ACTIVE_EVENT_CODE: str = "oas-2026"

    # QR signing-key placeholders (stage S5 will use real values). These are
    # intentionally unusable placeholders — never a real signing key.
    QR_SIGNING_KEY: str = "<set-QR_SIGNING_KEY-in-the-environment>"
    QR_KEY_ID: str = "<set-QR_KEY_ID-in-the-environment>"
    QR_ISSUER: str = "geekai-hub-01"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origin_list(self) -> List[str]:
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        for env_key in ("VERCEL_URL", "VERCEL_PROJECT_PRODUCTION_URL"):
            host = os.getenv(env_key, "").strip()
            if host:
                origin = host if host.startswith("http") else f"https://{host}"
                if origin not in origins:
                    origins.append(origin)
        return origins

    # SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@geekai.in"
    SMTP_USE_TLS: bool = True

    @property
    def smtp_configured(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_USER and self.SMTP_PASSWORD)

    # Uploads & Storage
    STORAGE_BACKEND: str = "local"  # "local" or "r2"
    UPLOAD_DIR: str = "/tmp/uploads" if os.getenv("VERCEL") else "uploads"

    # Global Cloudflare R2 Fallback (per-event settings override these)
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = ""
    R2_PUBLIC_URL: str = ""

    @property
    def r2_configured(self) -> bool:
        return bool(
            self.R2_ACCOUNT_ID
            and self.R2_ACCESS_KEY_ID
            and self.R2_SECRET_ACCESS_KEY
            and self.R2_BUCKET_NAME
        )

    # Cashfree Payment Gateway
    CASHFREE_APP_ID: str = ""
    CASHFREE_SECRET_KEY: str = ""
    CASHFREE_ENV: str = "sandbox"  # "sandbox" or "production"
    BACKEND_URL: str = "http://localhost:8000"

    @property
    def effective_backend_url(self) -> str:
        """Resolve public backend base URL, using Vercel deployment URL when BACKEND_URL is localhost."""
        if self.BACKEND_URL and not self.BACKEND_URL.startswith("http://localhost"):
            return self.BACKEND_URL.rstrip("/")
        vercel_host = os.getenv("VERCEL_PROJECT_PRODUCTION_URL") or os.getenv("VERCEL_URL")
        if vercel_host:
            return vercel_host if vercel_host.startswith("http") else f"https://{vercel_host}"
        return self.BACKEND_URL.rstrip("/")

    @property
    def cashfree_configured(self) -> bool:
        return bool(self.CASHFREE_APP_ID and self.CASHFREE_SECRET_KEY)

    @property
    def photos_dir(self) -> Path:
        p = Path(self.UPLOAD_DIR) / "photos"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def qrcodes_dir(self) -> Path:
        p = Path(self.UPLOAD_DIR) / "qrcodes"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def events_dir(self) -> Path:
        p = Path(self.UPLOAD_DIR) / "events"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def documents_dir(self) -> Path:
        p = Path(self.UPLOAD_DIR) / "documents"
        p.mkdir(parents=True, exist_ok=True)
        return p

    # Bootstrap forced password change: tracked via password_changed_at on
    # the users table (null = change required on next login). No column is
    # added here; the migration creates it.

    # Seed Admin / Super Admin (explicitly configured via environment; no insecure defaults)
    SEED_ADMIN_EMAIL: str = ""
    SEED_ADMIN_PASSWORD: str = ""
    SEED_ADMIN_NAME: str = "Super Admin"


settings = Settings()
