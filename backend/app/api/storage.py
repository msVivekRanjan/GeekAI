"""Storage API — presigned URL generation, local dev fallback upload, metadata tracking, and object deletion."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_staff, get_db
from app.core.security import decode_access_token
from app.models.models import Event, StoredFile, User, UserRole
from app.services import storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/storage", tags=["storage"])


class PresignUploadRequest(BaseModel):
    event_id: Optional[int] = None
    event_slug: Optional[str] = None
    participant_id: Optional[int] = None
    category: str  # participant_photos | form_uploads | documents | qr_codes
    filename: str
    content_type: str
    size_bytes: Optional[int] = None


class ConfirmUploadRequest(BaseModel):
    event_id: Optional[int] = None
    participant_id: Optional[int] = None
    category: str
    object_key: str
    public_url: str
    original_filename: Optional[str] = None
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    storage_provider: str = "r2"


class DeleteObjectRequest(BaseModel):
    event_id: Optional[int] = None
    object_key: str


@router.post("/presign-upload")
async def presign_upload(
    body: PresignUploadRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Generate a presigned upload URL for Cloudflare R2 (or local dev fallback).

    - `form_uploads` and `qr_codes` require authenticated admin/super-admin.
    - `participant_photos` and `documents` are allowed for active events.
    """
    if body.category in ("form_uploads", "qr_codes"):
        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Authentication required for this upload category")
        token = auth_header.split(" ", 1)[1].strip()
        try:
            claims = decode_access_token(token)
            role = claims.get("role")
            if role not in (UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value):
                raise HTTPException(status_code=403, detail="Admin privileges required")
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Resolve event by ID or slug
    event: Optional[Event] = None
    if body.event_id is not None:
        event = (await db.execute(select(Event).where(Event.id == body.event_id))).scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
    elif body.event_slug:
        event = (await db.execute(select(Event).where(Event.slug == body.event_slug))).scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

    if body.category in ("participant_photos", "documents") and event is not None:
        if not event.is_active:
            raise HTTPException(status_code=403, detail="Event is not active for registrations")

    descriptor = storage_service.create_presigned_upload(
        event=event,
        category=body.category,
        filename=body.filename,
        content_type=body.content_type,
        participant_id=body.participant_id,
        size_bytes=body.size_bytes,
    )
    return descriptor


@router.post("/local-upload")
async def local_upload(
    object_key: str = Form(...),
    file: UploadFile = File(...),
):
    """Local development fallback upload endpoint matching the presigned upload flow."""
    # Prevent path traversal
    cleaned = object_key.strip().lstrip("/")
    if ".." in cleaned or not cleaned.startswith("events/"):
        raise HTTPException(status_code=400, detail="Invalid object_key")

    parts = cleaned.split("/")
    category = parts[2] if len(parts) >= 3 else "documents"
    content = await file.read()
    storage_service.validate_upload(category, file.filename or cleaned, file.content_type, len(content))

    dest = Path(settings.UPLOAD_DIR) / cleaned
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)

    return {
        "object_key": cleaned,
        "public_url": f"/uploads/{cleaned}",
        "size_bytes": len(content),
        "storage_provider": "local",
    }


@router.post("/confirm-upload")
async def confirm_upload(
    body: ConfirmUploadRequest,
    db: AsyncSession = Depends(get_db),
):
    """Record uploaded file object_key and metadata in PostgreSQL."""
    existing = (await db.execute(
        select(StoredFile).where(StoredFile.object_key == body.object_key)
    )).scalar_one_or_none()
    if existing:
        return {"id": existing.id, "object_key": existing.object_key, "public_url": existing.public_url}

    record = StoredFile(
        event_id=body.event_id,
        participant_id=body.participant_id,
        category=body.category,
        object_key=body.object_key,
        public_url=body.public_url,
        original_filename=body.original_filename,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
        storage_provider=body.storage_provider,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return {"id": record.id, "object_key": record.object_key, "public_url": record.public_url}


@router.get("/object")
async def proxy_get_object(
    key: str = Query(...),
    event_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Proxy-serve an R2 or local object when no public R2 custom domain is configured."""
    if ".." in key:
        raise HTTPException(status_code=400, detail="Invalid object key")

    event = None
    if event_id is not None:
        event = (await db.execute(select(Event).where(Event.id == event_id))).scalar_one_or_none()

    data = storage_service.download_bytes(event, key)
    if data is None:
        raise HTTPException(status_code=404, detail="Object not found")

    ext = Path(key).suffix.lower()
    media_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".pdf": "application/pdf",
    }
    return Response(content=data, media_type=media_map.get(ext, "application/octet-stream"))


@router.delete("/object")
async def delete_stored_object(
    body: DeleteObjectRequest,
    db: AsyncSession = Depends(get_db),
    staff: User = Depends(get_current_staff),
):
    """Delete a replaced or unwanted object from R2/local storage and PostgreSQL."""
    if staff.role != UserRole.SUPER_ADMIN and staff.event_id:
        if body.event_id and body.event_id != staff.event_id:
            raise HTTPException(status_code=403, detail="Not authorized for this event")
        if f"events/{staff.event_id}/" not in body.object_key:
            raise HTTPException(status_code=403, detail="Not authorized for this object")

    event = None
    if body.event_id is not None:
        event = (await db.execute(select(Event).where(Event.id == body.event_id))).scalar_one_or_none()

    storage_service.delete_object(event, body.object_key)
    await db.execute(delete(StoredFile).where(StoredFile.object_key == body.object_key))
    await db.flush()
    return {"deleted": True, "object_key": body.object_key}
