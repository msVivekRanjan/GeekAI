"""Stage S1 security tests — 401/403/404/410 matrix and audit assertions.

DB-dependent tests skip cleanly when no disposable Postgres is reachable;
the anonymous/transport-only checks always run. This is the automated
backing for the curl matrix in docs/gates/G1.md.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.core.rate_limit import reset_rate_limits
from app.core.security import create_access_token, hash_password, token_claims
from app.models.audit import AuditLog
from app.models.models import Participant, User, UserRole
from tests.conftest import TEST_BOOTSTRAP_TOKEN

PII_ROUTES = [
    "/api/participants/",
    "/api/participants/1",
    "/api/participants/1/photo",
    "/api/participants/1/qrcode",
    "/api/sessions/",
    "/api/sessions/1",
    "/api/attendance/event",
    "/api/attendance/session/1",
    "/api/attendance/stats",
    "/api/embeddings/sync",
    "/api/admin/dashboard",
]


@pytest.fixture(autouse=True)
def _reset_limits():
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.mark.asyncio
@pytest.mark.parametrize("path", PII_ROUTES)
async def test_anonymous_pii_read_returns_401(client, path):
    response = await client.get(path)
    assert response.status_code == 401, f"{path} returned {response.status_code}"


@pytest.mark.asyncio
async def test_uploads_static_mount_is_gone(client):
    response = await client.get("/uploads/photos/1.jpg")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_login_without_credentials_returns_422(client):
    response = await client.post("/api/auth/login", json={})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# DB-dependent tests
# ---------------------------------------------------------------------------


async def _create_user(db_session, *, email: str, role: UserRole, name: str = "Test User") -> User:
    user = User(
        email=email,
        password_hash=hash_password("test-password-123"),
        name=name,
        role=role,
        password_changed_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    await db_session.commit()
    return user


def _token(user: User, *, event_ids=None, role=None) -> str:
    return create_access_token(
        token_claims(
            sub=user.id,
            role=role or user.role.value,
            event_ids=event_ids if event_ids is not None else [settings.ACTIVE_EVENT_CODE],
        )
    )


@pytest.mark.asyncio
async def test_volunteer_on_admin_route_returns_403(db_client, clean_tables):
    volunteer = await _create_user(clean_tables, email="volunteer@s1.example.com", role=UserRole.VOLUNTEER)
    token = _token(volunteer)
    response = await db_client.get(
        "/api/admin/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_wrong_event_scope_returns_403(db_client, clean_tables):
    staff = await _create_user(clean_tables, email="staff@s1.example.com", role=UserRole.VOLUNTEER)
    token = _token(staff, event_ids=["wrong-event"])
    response = await db_client.get(
        "/api/participants/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_valid_staff_can_read_participants(db_client, clean_tables):
    staff = await _create_user(clean_tables, email="reader@s1.example.com", role=UserRole.VOLUNTEER)
    token = _token(staff)
    response = await db_client.get(
        "/api/participants/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_legacy_validate_qr_returns_410(db_client, clean_tables):
    staff = await _create_user(clean_tables, email="scanner@s1.example.com", role=UserRole.VOLUNTEER)
    token = _token(staff)
    response = await db_client.post(
        "/api/attendance/validate-qr",
        json={"participant_id": 1, "name": "Nobody"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "LEGACY_QR_DISABLED"


@pytest.mark.asyncio
async def test_legacy_qrcode_read_returns_410(db_client, clean_tables):
    staff = await _create_user(clean_tables, email="qrreader@s1.example.com", role=UserRole.VOLUNTEER)
    token = _token(staff)
    response = await db_client.get(
        "/api/participants/1/qrcode",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "LEGACY_QR_DISABLED"


@pytest.mark.asyncio
async def test_bootstrap_flow(db_client, clean_tables, db_session):
    """Fresh DB: no login; bootstrap once; second bootstrap fails; change password."""
    # No users => no login possible.
    response = await db_client.post(
        "/api/auth/login",
        json={"email": "first@s1.example.com", "password": "whatever123"},
    )
    assert response.status_code == 401

    # Bootstrap creates exactly one admin.
    response = await db_client.post(
        "/api/auth/bootstrap",
        json={
            "token": TEST_BOOTSTRAP_TOKEN,
            "email": "first@s1.example.com",
            "password": "bootstrap-password-123",
            "name": "First Admin",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user"]["role"] == "ADMIN"
    assert body["must_change_password"] is True

    count = (await db_session.execute(select(func.count()).select_from(User))).scalar()
    assert count == 1

    # Second bootstrap attempt fails.
    response = await db_client.post(
        "/api/auth/bootstrap",
        json={
            "token": TEST_BOOTSTRAP_TOKEN,
            "email": "second@s1.example.com",
            "password": "bootstrap-password-456",
            "name": "Second Admin",
        },
    )
    assert response.status_code == 409

    # Invalid token fails with 403.
    response = await db_client.post(
        "/api/auth/bootstrap",
        json={
            "token": "wrong-token",
            "email": "third@s1.example.com",
            "password": "bootstrap-password-789",
            "name": "Third Admin",
        },
    )
    assert response.status_code == 403

    # First admin can log in, with forced-change flag.
    response = await db_client.post(
        "/api/auth/login",
        json={"email": "first@s1.example.com", "password": "bootstrap-password-123"},
    )
    assert response.status_code == 200
    assert response.json()["must_change_password"] is True

    # Change password clears the flag.
    token = response.json()["access_token"]
    response = await db_client.post(
        "/api/auth/change-password",
        json={
            "current_password": "bootstrap-password-123",
            "new_password": "new-password-456",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    response = await db_client.post(
        "/api/auth/login",
        json={"email": "first@s1.example.com", "password": "new-password-456"},
    )
    assert response.status_code == 200
    assert response.json()["must_change_password"] is False


@pytest.mark.asyncio
async def test_audit_rows_written_for_login_and_participant_read(db_client, clean_tables, db_session):
    staff = await _create_user(clean_tables, email="audit@s1.example.com", role=UserRole.VOLUNTEER)

    # Login writes LOGIN_SUCCEEDED (using a known password).
    # Recreate with known password via direct DB update.
    from app.core.security import hash_password as hp

    staff.password_hash = hp("audit-password-123")
    await clean_tables.commit()

    response = await db_client.post(
        "/api/auth/login",
        json={"email": "audit@s1.example.com", "password": "audit-password-123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    # Participant read writes PARTICIPANT_LIST_READ.
    response = await db_client.get(
        "/api/participants/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    actions = (
        await db_session.execute(select(AuditLog.action).order_by(AuditLog.id))
    ).scalars().all()
    assert "LOGIN_SUCCEEDED" in actions
    assert "PARTICIPANT_LIST_READ" in actions


@pytest.mark.asyncio
async def test_audit_redaction(db_client, clean_tables, db_session):
    """Audit rows must never contain raw email/phone from before/after."""
    from app.services.audit import audit_log

    await audit_log(
        clean_tables,
        action="TEST_REDACTION",
        actor_id=1,
        actor_role="ADMIN",
        after={"email": "secret@example.com", "phone": "+919876543210", "name": "Safe Name"},
    )
    await clean_tables.commit()

    row = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "TEST_REDACTION").order_by(AuditLog.id.desc())
        )
    ).scalar_one()
    assert "secret@example.com" not in row.after_json
    assert "+919876543210" not in row.after_json
    assert "Safe Name" in row.after_json
    assert "[REDACTED]" in row.after_json


@pytest.mark.asyncio
async def test_failed_auth_audit_rows_survive_rollback(db_client, clean_tables, db_session):
    """Failure paths must persist audit rows even though they raise and roll back.

    The request session rolls back on HTTPException; failure-path audit rows
    are written through a detached session so they remain queryable.
    """
    from app.core.security import hash_password as hp

    user = await _create_user(clean_tables, email="failed@s1.example.com", role=UserRole.VOLUNTEER)
    user.password_hash = hp("correct-password-123")
    await clean_tables.commit()

    # Wrong password -> 401, must write LOGIN_FAILED.
    response = await db_client.post(
        "/api/auth/login",
        json={"email": "failed@s1.example.com", "password": "wrong-password-999"},
    )
    assert response.status_code == 401

    # Invalid bootstrap token -> 403, must write BOOTSTRAP_FAILED.
    response = await db_client.post(
        "/api/auth/bootstrap",
        json={
            "token": "definitely-wrong-token",
            "email": "nobody@s1.example.com",
            "password": "bootstrap-password-123",
            "name": "Nobody",
        },
    )
    assert response.status_code == 403

    actions = (
        await db_session.execute(select(AuditLog.action).order_by(AuditLog.id))
    ).scalars().all()
    assert "LOGIN_FAILED" in actions
    assert "BOOTSTRAP_FAILED" in actions

    # Deactivated-account failure also persists its row.
    user.is_active = False
    await clean_tables.commit()
    response = await db_client.post(
        "/api/auth/login",
        json={"email": "failed@s1.example.com", "password": "correct-password-123"},
    )
    assert response.status_code == 403
    actions = (
        await db_session.execute(select(AuditLog.action).order_by(AuditLog.id))
    ).scalars().all()
    assert actions.count("LOGIN_FAILED") >= 2


@pytest.mark.asyncio
async def test_login_rate_limit_ignores_forwarded_for(db_client, clean_tables):
    """X-Forwarded-For must not bypass the per-IP login limit in S1."""
    reset_rate_limits()
    statuses = []
    last_response = None
    for i in range(6):
        last_response = await db_client.post(
            "/api/auth/login",
            json={"email": "ratelimit@s1.example.com", "password": "wrong-password-999"},
            headers={"X-Forwarded-For": f"198.51.100.{i + 1}"},
        )
        statuses.append(last_response.status_code)

    assert statuses == [401, 401, 401, 401, 401, 429], statuses
    assert last_response is not None
    assert last_response.headers.get("Retry-After")
    assert last_response.json()["detail"]["code"] == "RATE_LIMITED"
    reset_rate_limits()
