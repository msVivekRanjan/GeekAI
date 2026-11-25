"""Offline Sync API — Batch attendance sync and data download for the offline volunteer app.

Routes:
  POST /api/offline/sync/attendance  — Accept a batch of attendance records with local_uuid idempotency
  GET  /api/offline/participants     — Download participants + embeddings for pre-event caching
  GET  /api/offline/sessions         — Download sessions for pre-event caching
  GET  /api/offline/health           — Connectivity probe for the volunteer app
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_staff, get_db
from app.models.models import (
    Attendance,
    AttendanceMethod,
    FaceEmbedding,
    Participant,
    Session,
    User,
    Event,
    UserRole,
)
from app.schemas.schemas import (
    OfflineAttendanceRecord,
    OfflineSyncBatch,
    OfflineSyncResult,
    OfflineSyncResponse,
)

router = APIRouter(prefix="/api/offline", tags=["offline-sync"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Health probe
# ---------------------------------------------------------------------------

@router.get("/health")
async def offline_health():
    """Simple connectivity probe for the volunteer app."""
    return {"status": "online", "ts": datetime.now(timezone.utc).isoformat()}


# ---------------------------------------------------------------------------
# Participants download (for pre-event caching)
# ---------------------------------------------------------------------------

@router.get("/participants")
async def download_participants(
    event_id: int = Query(..., description="Event ID to download participants for"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_staff),
):
    """Return participants + their embeddings for the given event (for offline caching)."""
    # Verify the user has access to this event
    if current_user.role not in (UserRole.SUPER_ADMIN,):
        if current_user.event_id != event_id:
            raise HTTPException(status_code=403, detail="Access denied for this event")

    result = await db.execute(
        select(Participant).where(Participant.event_id == event_id, Participant.status == "CONFIRMED")
    )
    participants = result.scalars().all()

    # Fetch embeddings for all participants
    embeddings_map: dict[int, list[float]] = {}
    if participants:
        emb_result = await db.execute(
            select(FaceEmbedding).where(
                FaceEmbedding.participant_id.in_([p.id for p in participants])
            )
        )
        for emb in emb_result.scalars().all():
            if emb.embedding is not None:
                embeddings_map[emb.participant_id] = [float(x) for x in emb.embedding]

    out = []
    for p in participants:
        out.append({
            "id": p.id,
            "name": p.name,
            "email": p.email,
            "phone": getattr(p, "phone", None),
            "institution": getattr(p, "institution", None),
            "category": p.category.value if hasattr(p.category, "value") else p.category,
            "photo_url": p.photo_url,
            "photo_object_key": p.photo_object_key,
            "qr_code": p.qr_code_url,
            "event_id": p.event_id,
            "embedding": embeddings_map.get(p.id),
        })

    return {"event_id": event_id, "count": len(out), "participants": out}


# ---------------------------------------------------------------------------
# Sessions download (for pre-event caching)
# ---------------------------------------------------------------------------

@router.get("/sessions")
async def download_sessions(
    event_id: int = Query(..., description="Event ID to download sessions for"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_staff),
):
    """Return sessions for the given event (for offline caching)."""
    if current_user.role not in (UserRole.SUPER_ADMIN,):
        if current_user.event_id != event_id:
            raise HTTPException(status_code=403, detail="Access denied for this event")

    result = await db.execute(
        select(Session).where(Session.event_id == event_id).order_by(Session.start_time)
    )
    sessions = result.scalars().all()

    out = []
    for s in sessions:
        out.append({
            "id": s.id,
            "name": s.name,
            "event_id": s.event_id,
            "start_time": s.start_time.isoformat() if s.start_time else None,
            "end_time": s.end_time.isoformat() if s.end_time else None,
            "location": getattr(s, "location", None),
        })

    return {"event_id": event_id, "count": len(out), "sessions": out}


# ---------------------------------------------------------------------------
# Batch attendance sync
# ---------------------------------------------------------------------------

@router.post("/sync/attendance", response_model=OfflineSyncResponse)
async def sync_attendance_batch(
    body: OfflineSyncBatch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_staff),
):
    """Accept a batch of offline attendance records with local_uuid for idempotency.

    - Skips records whose local_uuid already exists in the DB (safe to retry).
    - Validates participant and session existence.
    - Prevents duplicate attendance for the same participant/session via existing constraints.
    - Returns per-record status.
    """
    results: list[OfflineSyncResult] = []

    for record in body.records:
        local_uuid_str = str(record.local_uuid)
        try:
            # 0. Enforce volunteer/admin event scope
            if current_user.role != UserRole.SUPER_ADMIN and current_user.event_id != record.event_id:
                results.append(OfflineSyncResult(
                    local_uuid=record.local_uuid,
                    status="error",
                    message=f"Access denied for event {record.event_id}",
                ))
                continue

            async with db.begin_nested():
                # 1. Check idempotency — already synced?
                existing = await db.execute(
                    select(Attendance).where(Attendance.local_uuid == record.local_uuid)
                )
                if existing.scalar_one_or_none():
                    results.append(OfflineSyncResult(
                        local_uuid=record.local_uuid,
                        status="already_synced",
                        message="Record already exists (idempotent skip)",
                    ))
                    continue

                # 2. Validate participant exists in the event
                part_result = await db.execute(
                    select(Participant).where(
                        Participant.id == record.participant_id,
                        Participant.event_id == record.event_id,
                    )
                )
                participant = part_result.scalar_one_or_none()
                if not participant:
                    results.append(OfflineSyncResult(
                        local_uuid=record.local_uuid,
                        status="error",
                        message=f"Participant {record.participant_id} not found in event {record.event_id}",
                    ))
                    continue

                # 3. Validate session if provided
                if record.session_id is not None:
                    sess_result = await db.execute(
                        select(Session).where(
                            Session.id == record.session_id,
                            Session.event_id == record.event_id,
                        )
                    )
                    if not sess_result.scalar_one_or_none():
                        results.append(OfflineSyncResult(
                            local_uuid=record.local_uuid,
                            status="error",
                            message=f"Session {record.session_id} not found in event {record.event_id}",
                        ))
                        continue

                # 4. Check for duplicate attendance (same participant + session)
                if record.session_id is None:
                    dup_stmt = select(Attendance).where(
                        Attendance.participant_id == record.participant_id,
                        Attendance.session_id.is_(None),
                    )
                else:
                    dup_stmt = select(Attendance).where(
                        Attendance.participant_id == record.participant_id,
                        Attendance.session_id == record.session_id,
                    )
                dup_check = await db.execute(dup_stmt)
                if dup_check.scalar_one_or_none():
                    results.append(OfflineSyncResult(
                        local_uuid=record.local_uuid,
                        status="duplicate",
                        message="Attendance already recorded for this participant/session",
                    ))
                    continue

                # 5. Validate method
                try:
                    method = AttendanceMethod(record.method.upper())
                except ValueError:
                    results.append(OfflineSyncResult(
                        local_uuid=record.local_uuid,
                        status="error",
                        message=f"Invalid method '{record.method}'. Must be FACE, QR, or MANUAL.",
                    ))
                    continue

                # 6. Parse marked_at
                marked_at = record.marked_at
                if isinstance(marked_at, str):
                    try:
                        marked_at = datetime.fromisoformat(marked_at.replace("Z", "+00:00"))
                    except ValueError:
                        marked_at = datetime.now(timezone.utc)
                if marked_at is None:
                    marked_at = datetime.now(timezone.utc)

                # 7. Create attendance record
                attendance = Attendance(
                    participant_id=record.participant_id,
                    session_id=record.session_id,
                    method=method,
                    marked_by=current_user.id,
                    marked_at=marked_at,
                    event_id=record.event_id,
                    local_uuid=record.local_uuid,
                    sync_source="offline",
                    synced_at=datetime.now(timezone.utc),
                )
                db.add(attendance)
                await db.flush()

                results.append(OfflineSyncResult(
                    local_uuid=record.local_uuid,
                    status="synced",
                    message="Successfully synced",
                    attendance_id=attendance.id,
                ))
                logger.info(
                    "Offline sync: participant=%d session=%s method=%s local_uuid=%s",
                    record.participant_id,
                    record.session_id,
                    record.method,
                    local_uuid_str,
                )

        except Exception as exc:
            logger.error("Offline sync error for local_uuid=%s: %s", local_uuid_str, exc)
            results.append(OfflineSyncResult(
                local_uuid=record.local_uuid,
                status="error",
                message=str(exc),
            ))
            continue

    await db.commit()

    synced = sum(1 for r in results if r.status == "synced")
    skipped = sum(1 for r in results if r.status in ("duplicate", "already_synced"))
    errors = sum(1 for r in results if r.status == "error")

    return OfflineSyncResponse(
        total=len(results),
        synced=synced,
        skipped=skipped,
        errors=errors,
        results=results,
    )
