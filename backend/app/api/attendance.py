"""Attendance API — record, query, validate QR (disabled).

Stage S1 protects every read with a staff principal and event scope, and
disables the legacy unsigned `validate-qr` path with 410. Response shapes
are unchanged.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_staff, get_db, require_event_scope
from app.models.models import (
    Attendance,
    AttendanceMethod,
    Participant,
    Session,
    User,
)
from app.schemas.schemas import (
    AttendanceCreate,
    AttendanceOut,
    AttendanceStats,
    ParticipantOut,
    QRValidateRequest,
    QRValidateResponse,
)
from app.services.audit import audit_log
from app.services.events import get_active_event_id

router = APIRouter(prefix="/api/attendance", tags=["attendance"])

_staff_event = get_current_staff


async def _audit(
    db: AsyncSession,
    request: Request,
    action: str,
    actor: User,
    entity: str = "attendance",
    entity_id: str | None = None,
    after: dict | None = None,
) -> None:
    await audit_log(
        db,
        action=action,
        actor_id=actor.id,
        actor_role=actor.role.value if hasattr(actor.role, "value") else actor.role,
        entity=entity,
        entity_id=entity_id,
        after=after,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/", response_model=AttendanceOut, status_code=status.HTTP_201_CREATED)
async def record_attendance(
    body: AttendanceCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_staff_event),
):
    """Record attendance for a participant. Prevents duplicates."""
    p_result = await db.execute(select(Participant).where(Participant.id == body.participant_id))
    participant = p_result.scalar_one_or_none()
    if not participant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")

    if body.session_id is not None:
        s_result = await db.execute(select(Session).where(Session.id == body.session_id))
        if not s_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if body.session_id is not None:
        dup_query = select(Attendance).where(
            and_(
                Attendance.participant_id == body.participant_id,
                Attendance.session_id == body.session_id,
            )
        )
    else:
        dup_query = select(Attendance).where(
            and_(
                Attendance.participant_id == body.participant_id,
                Attendance.session_id.is_(None),
            )
        )

    dup_result = await db.execute(dup_query)
    if dup_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attendance already recorded for this participant" + (
                f" in session {body.session_id}" if body.session_id else " at event level"
            ),
        )

    attendance = Attendance(
        participant_id=body.participant_id,
        session_id=body.session_id,
        method=body.method,
        marked_by=current_user.id,
        event_id=await get_active_event_id(db),
    )
    db.add(attendance)
    await db.flush()
    await db.refresh(attendance)
    await db.commit()

    await _audit(
        db,
        request,
        "ATTENDANCE_RECORDED",
        current_user,
        entity_id=str(attendance.id),
        after={
            "participant_id": body.participant_id,
            "session_id": body.session_id,
            "method": body.method.value,
        },
    )
    return AttendanceOut(
        id=attendance.id,
        participant_id=attendance.participant_id,
        session_id=attendance.session_id,
        method=attendance.method,
        marked_by=attendance.marked_by,
        marked_at=attendance.marked_at,
        participant_name=participant.name,
    )


@router.get("/event", response_model=list[AttendanceOut])
async def event_attendance(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(_staff_event),
):
    """List all event-level attendance (session_id IS NULL)."""
    result = await db.execute(
        select(Attendance, Participant.name)
        .join(Participant, Attendance.participant_id == Participant.id)
        .where(Attendance.session_id.is_(None))
        .order_by(Attendance.marked_at.desc())
    )
    rows = result.all()
    await _audit(db, request, "ATTENDANCE_LIST_READ", _staff, after={"scope": "event", "count": len(rows)})
    return [
        AttendanceOut(
            id=a.id,
            participant_id=a.participant_id,
            session_id=a.session_id,
            method=a.method,
            marked_by=a.marked_by,
            marked_at=a.marked_at,
            participant_name=name,
        )
        for a, name in rows
    ]


@router.get("/session/{session_id}", response_model=list[AttendanceOut])
async def session_attendance(
    session_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(_staff_event),
):
    """List all attendance records for a specific session."""
    s_result = await db.execute(select(Session).where(Session.id == session_id))
    if not s_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    result = await db.execute(
        select(Attendance, Participant.name, Session.name)
        .join(Participant, Attendance.participant_id == Participant.id)
        .outerjoin(Session, Attendance.session_id == Session.id)
        .where(Attendance.session_id == session_id)
        .order_by(Attendance.marked_at.desc())
    )
    rows = result.all()
    await _audit(
        db,
        request,
        "ATTENDANCE_SESSION_READ",
        _staff,
        entity_id=str(session_id),
        after={"count": len(rows)},
    )
    return [
        AttendanceOut(
            id=a.id,
            participant_id=a.participant_id,
            session_id=a.session_id,
            method=a.method,
            marked_by=a.marked_by,
            marked_at=a.marked_at,
            participant_name=p_name,
            session_name=s_name,
        )
        for a, p_name, s_name in rows
    ]


@router.get("/stats", response_model=AttendanceStats)
async def attendance_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(_staff_event),
):
    """Overall attendance statistics."""
    total_p = (await db.execute(select(func.count()).select_from(Participant))).scalar()
    total_checked = (
        await db.execute(
            select(func.count(func.distinct(Attendance.participant_id))).select_from(Attendance)
        )
    ).scalar()
    total_sessions = (await db.execute(select(func.count()).select_from(Session))).scalar()

    method_result = await db.execute(
        select(Attendance.method, func.count())
        .group_by(Attendance.method)
    )
    by_method = {row[0].value: row[1] for row in method_result.all()}

    session_result = await db.execute(
        select(Session.id, Session.name, func.count(Attendance.id))
        .outerjoin(Attendance, Attendance.session_id == Session.id)
        .group_by(Session.id, Session.name)
        .order_by(Session.start_time)
    )
    by_session = [
        {"session_id": sid, "session_name": sname, "count": cnt}
        for sid, sname, cnt in session_result.all()
    ]

    await _audit(db, request, "ATTENDANCE_STATS_READ", _staff, after={"scope": "aggregate"})
    return AttendanceStats(
        total_participants=total_p,
        total_checked_in=total_checked,
        total_sessions=total_sessions,
        attendance_by_method=by_method,
        attendance_by_session=by_session,
    )


@router.post("/validate-qr", response_model=QRValidateResponse)
async def validate_qr(
    body: QRValidateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(_staff_event),
):
    """Validate participant QR code and return participant details."""
    query = select(Participant).where(Participant.id == body.participant_id)
    if _staff.event_id:
        query = query.where(Participant.event_id == _staff.event_id)

    result = await db.execute(query)
    participant = result.scalar_one_or_none()
    if not participant:
        await _audit(
            db,
            request,
            "QR_VALIDATION_FAILED",
            _staff,
            entity="participant",
            entity_id=str(body.participant_id),
            after={"reason": "not_found"},
        )
        return QRValidateResponse(
            valid=False,
            participant=None,
            message="Participant not found or not registered for this event",
        )

    await _audit(
        db,
        request,
        "QR_VALIDATED",
        _staff,
        entity="participant",
        entity_id=str(participant.id),
        after={"valid": True, "name": participant.name},
    )
    return QRValidateResponse(
        valid=True,
        participant=ParticipantOut.model_validate(participant),
        message=f"Valid registration: {participant.name}",
    )
