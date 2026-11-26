"""Admin API — dashboard stats, data exports, volunteer and coupon management."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin, get_db
from app.core.security import hash_password
from app.models.models import (
    Attendance,
    Coupon,
    Event,
    Participant,
    ParticipantCategory,
    Session,
    User,
    UserRole,
)
from app.schemas.schemas import (
    CouponCreate,
    CouponOut,
    DashboardStats,
    ParticipantOut,
    VolunteerCreate,
    VolunteerOut,
)
from app.services.audit import audit_log

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def _audit(
    db: AsyncSession,
    request: Request,
    action: str,
    actor: User,
    entity: str,
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


@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    p_stmt = select(func.count()).select_from(Participant)
    s_stmt = select(func.count()).select_from(Session)
    a_stmt = select(func.count()).select_from(Attendance)
    c_stmt = (
        select(func.count())
        .select_from(Attendance)
        .where(Attendance.session_id.is_(None))
    )

    if _admin.event_id:
        p_stmt = p_stmt.where(Participant.event_id == _admin.event_id)
        s_stmt = s_stmt.where(Session.event_id == _admin.event_id)
        scoped_p = select(Participant.id).where(Participant.event_id == _admin.event_id)
        a_stmt = a_stmt.where(Attendance.participant_id.in_(scoped_p))
        c_stmt = c_stmt.where(Attendance.participant_id.in_(scoped_p))

    total_participants = (await db.execute(p_stmt)).scalar() or 0
    total_sessions = (await db.execute(s_stmt)).scalar() or 0
    total_attendance = (await db.execute(a_stmt)).scalar() or 0
    event_checkins = (await db.execute(c_stmt)).scalar() or 0

    # By category
    cat_stmt = select(Participant.category, func.count()).group_by(Participant.category)
    if _admin.event_id:
        cat_stmt = cat_stmt.where(Participant.event_id == _admin.event_id)
    cat_result = await db.execute(cat_stmt)
    by_category = {row[0].value: row[1] for row in cat_result.all()}

    # Recent registrations (last 10)
    recent_stmt = select(Participant).order_by(Participant.registered_at.desc()).limit(10)
    if _admin.event_id:
        recent_stmt = recent_stmt.where(Participant.event_id == _admin.event_id)
    recent_result = await db.execute(recent_stmt)
    recent = [ParticipantOut.model_validate(p) for p in recent_result.scalars().all()]

    await _audit(
        db,
        request,
        "ADMIN_DASHBOARD_READ",
        _admin,
        "dashboard",
        after={"event_id": _admin.event_id, "recent_count": len(recent)},
    )
    return DashboardStats(
        total_participants=total_participants,
        total_sessions=total_sessions,
        total_attendance_records=total_attendance,
        event_checkins=event_checkins,
        participants_by_category=by_category,
        recent_registrations=recent,
    )


@router.get("/event/form-schema")
async def get_admin_event_form_schema(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """Return the registration form schema for the admin's scoped event."""
    target_event_id = _admin.event_id or 1
    event = (await db.execute(select(Event).where(Event.id == target_event_id))).scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return {
        "event_id": event.id,
        "event_name": event.name,
        "cashfree_enabled": bool(event.cashfree_enabled),
        "schema": event.registration_form_schema,
    }


# ===== Volunteer Management =================================================

@router.get("/volunteers", response_model=list[VolunteerOut])
async def list_volunteers(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """List volunteers scoped to current event (or all if superadmin)."""
    stmt = (
        select(
            User,
            func.count(Attendance.id).label("attendance_count"),
        )
        .outerjoin(Attendance, Attendance.marked_by == User.id)
        .where(User.role == UserRole.VOLUNTEER)
    )
    if _admin.event_id:
        stmt = stmt.where(User.event_id == _admin.event_id)

    stmt = stmt.group_by(User.id).order_by(User.created_at.desc())
    result = await db.execute(stmt)
    rows = result.all()
    await _audit(db, request, "VOLUNTEER_LIST_READ", _admin, "user", after={"count": len(rows)})
    
    out = []
    for u, count in rows:
        evt_name = None
        if u.event_id:
            evt = (await db.execute(select(Event).where(Event.id == u.event_id))).scalar_one_or_none()
            if evt:
                evt_name = evt.name
        out.append(
            VolunteerOut(
                id=u.id,
                email=u.email,
                name=u.name,
                role=u.role,
                is_active=u.is_active,
                created_at=u.created_at,
                attendance_count=count,
                event_id=u.event_id,
                event_name=evt_name,
            )
        )
    return out


@router.post("/volunteers", response_model=VolunteerOut, status_code=status.HTTP_201_CREATED)
async def create_volunteer(
    body: VolunteerCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """Admin adds a new volunteer with custom email and password."""
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address already exists",
        )

    target_event_id = body.event_id or _admin.event_id or 1
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        name=body.name,
        role=UserRole.VOLUNTEER,
        event_id=target_event_id,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    evt = (await db.execute(select(Event).where(Event.id == target_event_id))).scalar_one_or_none()

    await _audit(db, request, "VOLUNTEER_CREATED", _admin, "user", str(user.id), {"role": user.role.value, "event_id": target_event_id})
    return VolunteerOut(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        attendance_count=0,
        event_id=user.event_id,
        event_name=evt.name if evt else None,
    )


@router.patch("/volunteers/{volunteer_id}/toggle-status", response_model=VolunteerOut)
async def toggle_volunteer_status(
    volunteer_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """Toggle a volunteer's active status."""
    stmt = select(User).where(User.id == volunteer_id, User.role == UserRole.VOLUNTEER)
    if _admin.event_id:
        stmt = stmt.where(User.event_id == _admin.event_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Volunteer not found")

    user.is_active = not user.is_active
    await db.flush()
    await db.refresh(user)

    count_result = await db.execute(
        select(func.count()).select_from(Attendance).where(Attendance.marked_by == user.id)
    )
    count = count_result.scalar() or 0

    evt_name = None
    if user.event_id:
        evt = (await db.execute(select(Event).where(Event.id == user.event_id))).scalar_one_or_none()
        if evt:
            evt_name = evt.name

    await _audit(db, request, "VOLUNTEER_STATUS_CHANGED", _admin, "user", str(volunteer_id), {"is_active": user.is_active})
    return VolunteerOut(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        attendance_count=count,
        event_id=user.event_id,
        event_name=evt_name,
    )


@router.delete("/volunteers/{volunteer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_volunteer(
    volunteer_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Remove a volunteer account, safely reassigning attendance logs to preserve history."""
    if volunteer_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own admin account",
        )

    stmt = select(User).where(User.id == volunteer_id, User.role == UserRole.VOLUNTEER)
    if admin.event_id:
        stmt = stmt.where(User.event_id == admin.event_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Volunteer not found")

    # Preserve attendance logs: reassign marked_by to the deleting admin
    await db.execute(
        text("UPDATE attendance SET marked_by = :admin_id WHERE marked_by = :vol_id"),
        {"admin_id": admin.id, "vol_id": volunteer_id},
    )
    # Clear any verified_by references
    await db.execute(
        text("UPDATE attendance SET verified_by = NULL WHERE verified_by = :vol_id"),
        {"vol_id": volunteer_id},
    )
    # Remove any qr_tokens issued by this volunteer
    await db.execute(
        text("DELETE FROM qr_tokens WHERE issued_by = :vol_id"),
        {"vol_id": volunteer_id},
    )

    await _audit(db, request, "VOLUNTEER_DELETED", admin, "user", str(volunteer_id), {"email": user.email, "name": user.name})
    await db.delete(user)
    await db.commit()


# ===== Coupon Management =====================================================

@router.get("/coupons", response_model=list[CouponOut])
async def list_coupons(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """List coupons for the admin's event."""
    query = select(Coupon)
    if _admin.event_id:
        query = query.where(Coupon.event_id == _admin.event_id)
    query = query.order_by(Coupon.created_at.desc())
    result = await db.execute(query)
    coupons = result.scalars().all()

    out = []
    for c in coupons:
        evt = (await db.execute(select(Event).where(Event.id == c.event_id))).scalar_one_or_none()
        out.append(
            CouponOut(
                id=c.id,
                code=c.code,
                event_id=c.event_id,
                event_name=evt.name if evt else None,
                description=c.description,
                max_uses=c.max_uses,
                used_count=c.used_count,
                is_active=c.is_active,
                created_at=c.created_at,
            )
        )
    return out


@router.post("/coupons", response_model=CouponOut, status_code=status.HTTP_201_CREATED)
async def create_coupon(
    body: CouponCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """Create a new coupon code (one-time or multi-use) for an event."""
    target_event_id = body.event_id or _admin.event_id or 1
    cleaned_code = body.code.strip().upper()

    existing = await db.execute(
        select(Coupon).where(
            Coupon.event_id == target_event_id,
            func.upper(Coupon.code) == cleaned_code,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Coupon code '{cleaned_code}' already exists for this event",
        )

    coupon = Coupon(
        code=cleaned_code,
        event_id=target_event_id,
        description=body.description,
        max_uses=body.max_uses,
        used_count=0,
        is_active=body.is_active,
    )
    db.add(coupon)
    await db.flush()
    await db.refresh(coupon)
    await db.commit()

    evt = (await db.execute(select(Event).where(Event.id == target_event_id))).scalar_one_or_none()
    await _audit(db, request, "COUPON_CREATED", _admin, "coupon", str(coupon.id), {"code": coupon.code, "event_id": target_event_id})

    return CouponOut(
        id=coupon.id,
        code=coupon.code,
        event_id=coupon.event_id,
        event_name=evt.name if evt else None,
        description=coupon.description,
        max_uses=coupon.max_uses,
        used_count=coupon.used_count,
        is_active=coupon.is_active,
        created_at=coupon.created_at,
    )


@router.patch("/coupons/{coupon_id}/toggle-status", response_model=CouponOut)
async def toggle_coupon_status(
    coupon_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """Toggle a coupon's active/inactive status."""
    stmt = select(Coupon).where(Coupon.id == coupon_id)
    if _admin.event_id:
        stmt = stmt.where(Coupon.event_id == _admin.event_id)
    result = await db.execute(stmt)
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coupon not found")

    coupon.is_active = not coupon.is_active
    await db.flush()
    await db.refresh(coupon)
    await db.commit()

    evt = (await db.execute(select(Event).where(Event.id == coupon.event_id))).scalar_one_or_none()
    await _audit(db, request, "COUPON_STATUS_CHANGED", _admin, "coupon", str(coupon_id), {"is_active": coupon.is_active})

    return CouponOut(
        id=coupon.id,
        code=coupon.code,
        event_id=coupon.event_id,
        event_name=evt.name if evt else None,
        description=coupon.description,
        max_uses=coupon.max_uses,
        used_count=coupon.used_count,
        is_active=coupon.is_active,
        created_at=coupon.created_at,
    )


@router.delete("/coupons/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_coupon(
    coupon_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """Delete a coupon code."""
    stmt = select(Coupon).where(Coupon.id == coupon_id)
    if _admin.event_id:
        stmt = stmt.where(Coupon.event_id == _admin.event_id)
    result = await db.execute(stmt)
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coupon not found")

    await _audit(db, request, "COUPON_DELETED", _admin, "coupon", str(coupon_id), {"code": coupon.code})
    await db.delete(coupon)
    await db.commit()


# ===== Export Data ===========================================================

@router.get("/export/participants")
async def export_participants(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """Export participants as CSV, scoped to the admin's event."""
    stmt = select(Participant).order_by(Participant.id)
    if _admin.event_id:
        stmt = stmt.where(Participant.event_id == _admin.event_id)
    result = await db.execute(stmt)
    participants = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Email", "Phone", "Institution", "Category", "Payment Status", "Coupon Code", "Registered At"])
    for p in participants:
        writer.writerow([
            p.id,
            p.name,
            p.email,
            p.phone or "",
            p.institution or "",
            p.category.value,
            p.payment_status or "PENDING",
            p.coupon_code or "",
            p.registered_at.isoformat(),
        ])
    output.seek(0)

    filename = f"participants_event_{_admin.event_id or 'all'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    await _audit(db, request, "EXPORT_PARTICIPANTS_CSV", _admin, "export", after={"count": len(participants), "event_id": _admin.event_id})
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/attendance")
async def export_attendance(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """Export attendance as CSV, scoped to the admin's event."""
    stmt = (
        select(Attendance, Participant.name, Session.name)
        .join(Participant, Attendance.participant_id == Participant.id)
        .outerjoin(Session, Attendance.session_id == Session.id)
        .order_by(Attendance.marked_at.desc())
    )
    if _admin.event_id:
        stmt = stmt.where(Participant.event_id == _admin.event_id)

    result = await db.execute(stmt)
    rows = result.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Attendance ID", "Participant ID", "Participant Name", "Session", "Method", "Marked At"])
    for att, p_name, s_name in rows:
        writer.writerow([
            att.id,
            att.participant_id,
            p_name,
            s_name or "Event Check-in",
            att.method.value,
            att.marked_at.isoformat(),
        ])
    output.seek(0)

    filename = f"attendance_event_{_admin.event_id or 'all'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    await _audit(db, request, "EXPORT_ATTENDANCE_CSV", _admin, "export", after={"count": len(rows), "event_id": _admin.event_id})
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/excel")
async def export_excel(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """Export participants and attendance in a multi-sheet Excel file."""
    p_stmt = select(Participant).order_by(Participant.id)
    if _admin.event_id:
        p_stmt = p_stmt.where(Participant.event_id == _admin.event_id)
    p_result = await db.execute(p_stmt)
    participants = p_result.scalars().all()

    a_stmt = (
        select(Attendance, Participant.name, Session.name)
        .join(Participant, Attendance.participant_id == Participant.id)
        .outerjoin(Session, Attendance.session_id == Session.id)
        .order_by(Attendance.marked_at.desc())
    )
    if _admin.event_id:
        a_stmt = a_stmt.where(Participant.event_id == _admin.event_id)
    a_result = await db.execute(a_stmt)
    attendance_rows = a_result.all()

    wb = Workbook()

    # Sheet 1: Participants
    ws_p = wb.active
    ws_p.title = "Participants"
    ws_p.append(["ID", "Name", "Email", "Phone", "Institution", "Category", "Payment Status", "Coupon Code", "Registered At"])
    for p in participants:
        ws_p.append([
            p.id,
            p.name,
            p.email,
            p.phone or "",
            p.institution or "",
            p.category.value,
            p.payment_status or "PENDING",
            p.coupon_code or "",
            p.registered_at.strftime("%Y-%m-%d %H:%M:%S"),
        ])

    # Sheet 2: Attendance
    ws_a = wb.create_sheet(title="Attendance")
    ws_a.append(["Attendance ID", "Participant ID", "Participant Name", "Session", "Method", "Marked At"])
    for att, p_name, s_name in attendance_rows:
        ws_a.append([
            att.id,
            att.participant_id,
            p_name,
            s_name or "Event Check-in",
            att.method.value,
            att.marked_at.strftime("%Y-%m-%d %H:%M:%S"),
        ])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"geekai_event_{_admin.event_id or 'all'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    await _audit(db, request, "EXPORT_EXCEL", _admin, "export", after={"participants": len(participants), "attendance": len(attendance_rows), "event_id": _admin.event_id})
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
