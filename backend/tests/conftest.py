"""Shared pytest fixtures for the backend baseline.

The S0 suite deliberately does not start the production lifespan. The
lifespan runs Alembic and seeds users, neither of which belongs in a unit test
and neither of which is safe without a disposable database. `httpx`'s
ASGITransport calls the ASGI app directly and does not invoke lifespan, so the
health/OpenAPI tests exercise the real route table without a database.

Stage S1 adds DB-dependent security tests. They are **opt-in** via the
`GEEKAI_TEST_DB=1` environment flag; by default they skip cleanly so a local
run never touches an unrelated Postgres that happens to be listening on the
default port. `DATABASE_URL` reachability is a secondary guard. CI sets
`GEEKAI_TEST_DB: "1"` and provides a disposable PostgreSQL database, with
`alembic upgrade head` run before pytest.
"""

from __future__ import annotations

import os
import socket
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pytest
from sqlalchemy import text

# Set these before importing app.main: settings and the SQLAlchemy engine are
# created at import time. No connection is opened by the tests.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/geekai_test")
os.environ.setdefault("SECRET_KEY", "s0-test-secret-not-for-production")
os.environ.setdefault("BOOTSTRAP_TOKEN", "s1-test-bootstrap-token-not-for-production")
os.environ.setdefault("UPLOAD_DIR", str(Path(tempfile.gettempdir()) / "geekai-s0-uploads"))
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

TEST_BOOTSTRAP_TOKEN = os.environ["BOOTSTRAP_TOKEN"]


@pytest.fixture(scope="session")
def app():
    from app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


def _database_reachable() -> bool:
    """Return True if DATABASE_URL points to a reachable, real database.

    Uses a plain socket check rather than an async driver so no event loop is
    created/closed at collection time (which would strand pooled connections
    bound to the closed loop).
    """
    url = os.environ.get("DATABASE_URL", "")
    if not url or "<" in url:
        return False
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def database_available() -> bool:
    """DB tests are opt-in: require GEEKAI_TEST_DB=1 AND a reachable database."""
    if os.environ.get("GEEKAI_TEST_DB", "").strip() != "1":
        return False
    return _database_reachable()


@pytest.fixture
async def db_client(app, database_available):
    """Async client for DB-dependent tests; skips if no database is reachable."""
    if not database_available:
        pytest.skip("DB test skipped; set GEEKAI_TEST_DB=1 with a reachable disposable DATABASE_URL")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


@pytest.fixture
async def db_session(database_available):
    """Direct DB session for assertions; skips if no database is reachable."""
    if not database_available:
        pytest.skip("DB test skipped; set GEEKAI_TEST_DB=1 with a reachable disposable DATABASE_URL")
    from app.core.deps import async_session_factory

    async with async_session_factory() as session:
        yield session


@pytest.fixture
async def clean_tables(db_session):
    """Truncate all audit/user data before a DB test to keep tests isolated."""
    from sqlalchemy import text

    # Truncate every table written by S0-S2, including the S2 additions.
    await db_session.execute(text("TRUNCATE TABLE audit_log RESTART IDENTITY CASCADE"))
    await db_session.execute(text("TRUNCATE TABLE email_outbox RESTART IDENTITY CASCADE"))
    await db_session.execute(text("TRUNCATE TABLE sync_batches RESTART IDENTITY CASCADE"))
    await db_session.execute(text("TRUNCATE TABLE qr_tokens RESTART IDENTITY CASCADE"))
    await db_session.execute(text("TRUNCATE TABLE registration_jobs RESTART IDENTITY CASCADE"))
    await db_session.execute(text("TRUNCATE TABLE attendance RESTART IDENTITY CASCADE"))
    await db_session.execute(text("TRUNCATE TABLE participants RESTART IDENTITY CASCADE"))
    await db_session.execute(text("TRUNCATE TABLE sessions RESTART IDENTITY CASCADE"))
    await db_session.execute(text("TRUNCATE TABLE events RESTART IDENTITY CASCADE"))
    await db_session.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
    await db_session.commit()
    yield db_session
