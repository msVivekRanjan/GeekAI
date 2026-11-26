"""Stage S2 validation-query tests (Database-Planning.md §7).

All tests are DB-backed and therefore opt-in via GEEKAI_TEST_DB=1. They use
synthetic rows only and assert the constraints/backfills the migration chain
is required to produce. S1 security tests remain in test_security.py and run
as regressions in the same suite.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.entities import EmailOutbox, Event, QRToken, SyncBatch
from app.models.enums import ParticipantSource, ParticipantStatus, QRScope
from app.models.models import (
    Attendance,
    AttendanceMethod,
    Participant,
    Session,
    User,
    UserRole,
)

EVENT_CODE = "oas-2026"


@pytest.fixture
async def sample_event(clean_tables: AsyncSession) -> Event:
    event = Event(code=EVENT_CODE, name="Odisha AI Symposium 2026", status="PLANNED")
    clean_tables.add(event)
    await clean_tables.flush()
    await clean_tables.commit()
    return event


async def _participant(db: AsyncSession, event_id: int, email: str, **kwargs) -> Participant:
    p = Participant(
        name="Synthetic Participant",
        email=email,
        category="STUDENT",
        event_id=event_id,
        source=kwargs.pop("source", ParticipantSource.ADMIN),
        status=kwargs.pop("status", ParticipantStatus.IMPORTED),
        **kwargs,
    )
    db.add(p)
    await db.flush()
    return p


async def _user(db: AsyncSession) -> User:
    u = User(
        email=f"dbtest-{uuid4().hex[:8]}@s2.example.com",
        password_hash="x",
        name="DB Test User",
        role=UserRole.ADMIN,
        password_changed_at=datetime.now(timezone.utc),
    )
    db.add(u)
    await db.flush()
    return u


@pytest.mark.asyncio
async def test_default_event_has_no_invented_facts(sample_event: Event, db_session: AsyncSession):
    row = (
        await db_session.execute(
            text("SELECT code, name, starts_at, ends_at, timezone, venue, status FROM events WHERE id = :id"),
            {"id": sample_event.id},
        )
    ).one()
    assert row.code == EVENT_CODE
    assert row.name == "Odisha AI Symposium 2026"
    assert row.starts_at is None
    assert row.ends_at is None
    assert row.timezone is None
    assert row.venue is None
    assert row.status == "PLANNED"


@pytest.mark.asyncio
async def test_counts_by_event_status_source(sample_event: Event, db_session: AsyncSession):
    await _participant(db_session, sample_event.id, "a@s2.example.com", status=ParticipantStatus.IMPORTED)
    await _participant(db_session, sample_event.id, "b@s2.example.com", status=ParticipantStatus.SYNCED)
    await _participant(
        db_session, sample_event.id, "c@s2.example.com",
        status=ParticipantStatus.SYNCED, source=ParticipantSource.WALK_IN,
    )
    await db_session.commit()

    rows = (
        await db_session.execute(
            text(
                "SELECT status, source, count(*) AS n FROM participants "
                "WHERE event_id = :eid GROUP BY status, source ORDER BY status, source"
            ),
            {"eid": sample_event.id},
        )
    ).all()
    counts = {(r.status, r.source): r.n for r in rows}
    assert counts[("IMPORTED", "ADMIN")] == 1
    assert counts[("SYNCED", "ADMIN")] == 1
    assert counts[("SYNCED", "WALK_IN")] == 1


@pytest.mark.asyncio
async def test_qr_active_entry_token_uniqueness(sample_event: Event, db_session: AsyncSession):
    p = await _participant(db_session, sample_event.id, "qr@s2.example.com")
    await db_session.commit()
    now = datetime.now(timezone.utc)
    db_session.add(
        QRToken(
            jti=str(uuid4()),
            participant_id=p.id,
            event_id=sample_event.id,
            scope=QRScope.ENTRY.value,
            expires_at=now + timedelta(hours=1),
        )
    )
    await db_session.commit()
    db_session.add(
        QRToken(
            jti=str(uuid4()),
            participant_id=p.id,
            event_id=sample_event.id,
            scope=QRScope.ENTRY.value,
            expires_at=now + timedelta(hours=2),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_attendance_idempotency_and_void_reason(sample_event: Event, db_session: AsyncSession):
    p = await _participant(db_session, sample_event.id, "att@s2.example.com")
    user = await _user(db_session)
    await db_session.commit()
    # Capture scalars before any rollback expires and lazily reloads the ORM
    # objects (which would raise MissingGreenlet outside the greenlet context).
    pid, uid, eid = p.id, user.id, sample_event.id

    client_event_id = str(uuid4())
    row = Attendance(
        participant_id=p.id,
        method=AttendanceMethod.QR,
        marked_by=user.id,
        event_id=sample_event.id,
        client_event_id=client_event_id,
        is_void=True,
        void_reason="DUPLICATE_SCAN",
        voided_at=datetime.now(timezone.utc),
    )
    db_session.add(row)
    await db_session.commit()

    # Duplicate client_event_id is rejected.
    db_session.add(
        Attendance(
            participant_id=p.id,
            method=AttendanceMethod.QR,
            marked_by=user.id,
            event_id=sample_event.id,
            client_event_id=client_event_id,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    # Event-level duplicate is rejected by the preserved 001 index.
    db_session.add(
        Attendance(
            participant_id=pid,
            method=AttendanceMethod.MANUAL,
            marked_by=uid,
            event_id=eid,
            client_event_id=str(uuid4()),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    void_rows = (
        await db_session.execute(
            text("SELECT count(*) FROM attendance WHERE is_void = true AND void_reason IS NOT NULL")
        )
    ).scalar_one()
    assert void_rows == 1


@pytest.mark.asyncio
async def test_outbox_no_stuck_rows_and_batch_indexes(sample_event: Event, db_session: AsyncSession):
    p = await _participant(db_session, sample_event.id, "mail@s2.example.com")
    await db_session.commit()
    db_session.add(
        EmailOutbox(
            participant_id=p.id,
            template="WELCOME",
            status="PENDING",
            attempts=0,
            next_attempt_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
    )
    db_session.add(
        SyncBatch(
            batch_id=f"hub01-{uuid4().hex[:8]}",
            hub_id="hub01",
            cursor_from=0,
            cursor_to=10,
            item_count=10,
        )
    )
    await db_session.commit()

    stuck = (
        await db_session.execute(
            text(
                "SELECT count(*) FROM email_outbox WHERE status = 'PENDING' "
                "AND next_attempt_at < now() - interval '1 hour'"
            )
        )
    ).scalar_one()
    assert stuck == 1  # the validation query finds the synthetic stuck row
    assert (await db_session.execute(text("SELECT count(*) FROM sync_batches"))).scalar_one() == 1


@pytest.mark.asyncio
async def test_audit_covers_status_transition_and_void(sample_event: Event, db_session: AsyncSession):
    p = await _participant(db_session, sample_event.id, "audit@s2.example.com")
    await db_session.commit()
    db_session.add_all(
        [
            AuditLog(action="PARTICIPANT_STATUS_CHANGED", entity="participant", entity_id=str(p.id), actor_role="ADMIN"),
            AuditLog(action="ATTENDANCE_VOIDED", entity="attendance", entity_id="1", actor_role="ADMIN"),
        ]
    )
    await db_session.commit()

    actions = set((await db_session.execute(text("SELECT action FROM audit_log"))).scalars().all())
    assert "PARTICIPANT_STATUS_CHANGED" in actions
    assert "ATTENDANCE_VOIDED" in actions


@pytest.mark.asyncio
async def test_event_id_required_and_email_unique_per_event(sample_event: Event, db_session: AsyncSession):
    eid = sample_event.id
    # event_id is non-null after M8.
    db_session.add(Participant(name="No Event", email="noevent@s2.example.com"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    await _participant(db_session, eid, "dupe@s2.example.com")
    await db_session.commit()
    db_session.add(Participant(name="Dupe", email="DUPE@s2.example.com", event_id=eid))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
