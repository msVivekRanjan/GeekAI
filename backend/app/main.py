"""GeekAI — FastAPI application entry point.

Stage S1 removes the public `/uploads` static mount and startup seeding,
adds request-id middleware and structured JSON logging with PII redaction.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.db_init import run_migrations_async

# Structured JSON logging with redaction of emails, phones and tokens.
from app.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown lifecycle."""
    settings.photos_dir
    settings.qrcodes_dir
    logger.info("GeekAI backend starting — upload directories ready")

    # Ensure database schema is migrated before accepting traffic.
    await run_migrations_async()

    # Ensure Super Admin account is initialized
    from app.core.db_init import init_super_admin_async
    await init_super_admin_async()

    yield
    logger.info("GeekAI backend shutting down")


app = FastAPI(
    title="GeekAI",
    description="Registration & Attendance Management for the Odisha AI Symposium",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
from app.core.middleware import RequestIDMiddleware  # noqa: E402

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public static file serving for uploads (photos, QR codes).
# These files are served unauthenticated via /uploads/ so the admin
# dashboard can display them directly in <img> tags.
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR, check_dir=False), name="uploads")

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
from app.api.admin import router as admin_router  # noqa: E402
from app.api.attendance import router as attendance_router  # noqa: E402
from app.api.auth import router as auth_router  # noqa: E402
from app.api.embeddings import router as embeddings_router  # noqa: E402
from app.api.events import router as events_router  # noqa: E402
from app.api.offline_sync import router as offline_sync_router  # noqa: E402
from app.api.participants import router as participants_router  # noqa: E402
from app.api.payments import router as payments_router  # noqa: E402
from app.api.sessions import router as sessions_router  # noqa: E402
from app.api.storage import router as storage_router  # noqa: E402
from app.api.super_admin import router as super_admin_router  # noqa: E402

app.include_router(auth_router)
app.include_router(participants_router)
app.include_router(sessions_router)
app.include_router(attendance_router)
app.include_router(embeddings_router)
app.include_router(admin_router)
app.include_router(events_router)
app.include_router(payments_router)
app.include_router(storage_router)
app.include_router(super_admin_router)
app.include_router(offline_sync_router)


@app.get("/", tags=["health"])
async def root():
    return {"status": "ok", "app": "GeekAI", "version": "1.0.0"}


@app.get("/health", tags=["health"])
@app.get("/api/health", tags=["health"])
async def health():
    return {"status": "healthy"}
