"""Tests for volunteer deletion and historical attendance preservation."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.models.models import Attendance, AttendanceMethod, Event, Participant, User, UserRole


@pytest.mark.asyncio
async def test_delete_volunteer_preserves_attendance_and_revokes_access(
    db_client,
    clean_tables,
    sample_event: Event,
):
    admin = User(
        email="admin@voltest.example.com",
        password_hash=hash_password("AdminPass123!"),
        name="Event Admin",
        role=UserRole.ADMIN,
        is_active=True,
        event_id=sample_event.id,
    )
    volunteer = User(
        email="vol@voltest.example.com",
        password_hash=hash_password("VolPass123!"),
        name="Temp Volunteer",
        role=UserRole.VOLUNTEER,
        is_active=True,
        event_id=sample_event.id,
    )
    clean_tables.add_all([admin, volunteer])
    await clean_tables.flush()

    participant = Participant(
        name="Attendee One",
        email="attendee@voltest.example.com",
        category="STUDENT",
        event_id=sample_event.id,
        status="CONFIRMED",
    )
    clean_tables.add(participant)
    await clean_tables.flush()

    attendance = Attendance(
        participant_id=participant.id,
        session_id=None,
        method=AttendanceMethod.QR,
        marked_by=volunteer.id,
        event_id=sample_event.id,
    )
    clean_tables.add(attendance)
    await clean_tables.commit()

    admin_token = create_access_token({"sub": str(admin.id), "role": "ADMIN", "event_ids": ["oas-2026"]})
    vol_token = create_access_token({"sub": str(volunteer.id), "role": "VOLUNTEER", "event_ids": ["oas-2026"]})

    # Delete volunteer
    resp = await db_client.delete(
        f"/api/admin/volunteers/{volunteer.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 204

    # Historical attendance is preserved and reassigned to admin
    att_row = (
        await clean_tables.execute(select(Attendance).where(Attendance.id == attendance.id))
    ).scalar_one_or_none()
    assert att_row is not None
    assert att_row.marked_by == admin.id

    # Deleted volunteer's token is rejected (portal access revoked)
    stats_resp = await db_client.get(
        "/api/attendance/stats",
        headers={"Authorization": f"Bearer {vol_token}"},
    )
    assert stats_resp.status_code == 401
