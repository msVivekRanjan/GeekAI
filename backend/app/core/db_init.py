"""Database migration and initialization service."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_alembic_config() -> Config:
    """Resolve and configure Alembic config pointing to backend directory."""
    # Look for alembic.ini relative to this file's hierarchy or working directory
    current_dir = Path(__file__).resolve().parent  # app/core
    backend_dir = current_dir.parent.parent        # backend

    ini_candidates = [
        backend_dir / "alembic.ini",
        Path.cwd() / "alembic.ini",
        Path.cwd() / "backend" / "alembic.ini",
    ]

    ini_path = None
    for candidate in ini_candidates:
        if candidate.is_file():
            ini_path = candidate
            break

    if not ini_path:
        raise FileNotFoundError("Could not find alembic.ini in project directories")

    alembic_cfg = Config(str(ini_path))
    # Ensure migrations directory is resolved relative to alembic.ini
    migrations_dir = ini_path.parent / "migrations"
    alembic_cfg.set_main_option("script_location", str(migrations_dir))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    return alembic_cfg


def run_migrations(max_retries: int = 5, retry_interval: float = 2.0) -> None:
    """Run Alembic migrations to the latest revision (head).

    Includes retry logic to handle cases where PostgreSQL is still initializing.
    """
    alembic_cfg = get_alembic_config()
    logger.info("Applying database migrations (alembic upgrade head)...")

    for attempt in range(1, max_retries + 1):
        try:
            command.upgrade(alembic_cfg, "head")
            logger.info("Database migrations applied successfully.")
            return
        except Exception as exc:
            if "Can't locate revision" in str(exc):
                logger.warning("Unknown revision in database schema, synchronizing with stamp head...")
                try:
                    command.stamp(alembic_cfg, "head", purge=True)
                    command.upgrade(alembic_cfg, "head")
                    logger.info("Database migrations synchronized and applied successfully.")
                    return
                except Exception as inner_exc:
                    logger.error("Failed to recover revision sync: %s", inner_exc)
            if attempt < max_retries:
                logger.warning(
                    "Database migration attempt %d/%d failed: %s. Retrying in %.1fs...",
                    attempt,
                    max_retries,
                    exc,
                    retry_interval,
                )
                time.sleep(retry_interval)
            else:
                logger.error("Failed to apply database migrations after %d attempts: %s", max_retries, exc)
                raise exc


async def run_migrations_async() -> None:
    """Asynchronously execute migrations in a worker thread so the event loop is unblocked."""
    await asyncio.to_thread(run_migrations)


async def init_super_admin_async() -> None:
    """Ensure the Super Admin user exists and has the correct password and role."""
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.core.deps import async_session_factory
    from app.core.security import hash_password, verify_password
    from app.models.models import User, UserRole

    async with async_session_factory() as db:
        res = await db.execute(select(User).where(User.email == settings.SEED_ADMIN_EMAIL))
        user = res.scalar_one_or_none()
        if not user:
            user = User(
                email=settings.SEED_ADMIN_EMAIL,
                password_hash=hash_password(settings.SEED_ADMIN_PASSWORD),
                name=settings.SEED_ADMIN_NAME,
                role=UserRole.SUPER_ADMIN,
                is_active=True,
                event_id=None,
                password_changed_at=datetime.now(timezone.utc),
            )
            db.add(user)
            await db.commit()
            logger.info("Created default Super Admin account: %s", settings.SEED_ADMIN_EMAIL)
        else:
            updated = False
            if user.role != UserRole.SUPER_ADMIN:
                user.role = UserRole.SUPER_ADMIN
                updated = True
            if user.event_id is not None:
                user.event_id = None
                updated = True
            if not user.is_active:
                user.is_active = True
                updated = True
            if not verify_password(settings.SEED_ADMIN_PASSWORD, user.password_hash):
                user.password_hash = hash_password(settings.SEED_ADMIN_PASSWORD)
                user.password_changed_at = datetime.now(timezone.utc)
                updated = True
            if updated:
                await db.commit()
                logger.info("Synchronized Super Admin account (%s) with SUPER_ADMIN role and credentials", settings.SEED_ADMIN_EMAIL)


