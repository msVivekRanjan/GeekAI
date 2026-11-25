"""Unified storage service supporting Cloudflare R2 (S3-compatible) and local filesystem fallback."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.models import Event

logger = logging.getLogger(__name__)

ALLOWED_CATEGORIES = {
    "participant_photos": {
        "extensions": {".jpg", ".jpeg", ".png", ".webp", ".gif"},
        "mime_prefixes": ("image/",),
        "max_bytes": 5 * 1024 * 1024,  # 5 MB
    },
    "form_uploads": {
        "extensions": {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".pdf", ".doc", ".docx", ".txt", ".csv", ".xlsx", ".zip"},
        "mime_prefixes": ("image/", "application/pdf", "application/", "text/"),
        "max_bytes": 15 * 1024 * 1024,  # 15 MB
    },
    "documents": {
        "extensions": {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf", ".doc", ".docx", ".txt", ".csv", ".xlsx", ".zip"},
        "mime_prefixes": ("image/", "application/pdf", "application/", "text/"),
        "max_bytes": 15 * 1024 * 1024,  # 15 MB
    },
    "qr_codes": {
        "extensions": {".png"},
        "mime_prefixes": ("image/png",),
        "max_bytes": 2 * 1024 * 1024,  # 2 MB
    },
}


@dataclass
class R2Config:
    account_id: str
    access_key_id: str
    secret_access_key: str
    bucket_name: str
    public_url: Optional[str] = None


def resolve_r2_config(event: Optional[Event]) -> Optional[R2Config]:
    """Resolve Cloudflare R2 credentials for an event, falling back to global settings or None (local)."""
    if (
        event is not None
        and getattr(event, "r2_enabled", False)
        and event.r2_account_id
        and event.r2_access_key_id
        and event.r2_secret_access_key
        and event.r2_bucket_name
    ):
        return R2Config(
            account_id=event.r2_account_id.strip(),
            access_key_id=event.r2_access_key_id.strip(),
            secret_access_key=event.r2_secret_access_key.strip(),
            bucket_name=event.r2_bucket_name.strip(),
            public_url=event.r2_public_url.strip() if event.r2_public_url else None,
        )

    if settings.STORAGE_BACKEND.strip().lower() == "r2" and settings.r2_configured:
        return R2Config(
            account_id=settings.R2_ACCOUNT_ID.strip(),
            access_key_id=settings.R2_ACCESS_KEY_ID.strip(),
            secret_access_key=settings.R2_SECRET_ACCESS_KEY.strip(),
            bucket_name=settings.R2_BUCKET_NAME.strip(),
            public_url=settings.R2_PUBLIC_URL.strip() if settings.R2_PUBLIC_URL else None,
        )

    return None


def _get_s3_client(cfg: R2Config):
    """Construct a boto3 S3 client pointed at Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=f"https://{cfg.account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=cfg.access_key_id,
        aws_secret_access_key=cfg.secret_access_key,
        config=BotoConfig(signature_version="s3v4"),
        region_name="auto",
    )


def sanitize_filename(filename: str) -> str:
    """Strip path components and unsafe characters from a filename."""
    base = Path(filename or "file").name
    stem = re.sub(r"[^a-zA-Z0-9._-]", "_", base)
    return stem[:120] or "file"


def validate_upload(
    category: str,
    filename: str,
    content_type: Optional[str] = None,
    size_bytes: Optional[int] = None,
) -> str:
    """Validate upload category, extension, MIME type, and file size. Returns normalized extension."""
    if category not in ALLOWED_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid upload category '{category}'. Allowed: {', '.join(ALLOWED_CATEGORIES.keys())}",
        )

    rules = ALLOWED_CATEGORIES[category]
    ext = Path(filename or "").suffix.lower()
    if not ext or ext not in rules["extensions"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File extension '{ext}' not allowed for '{category}'. Allowed: {', '.join(sorted(rules['extensions']))}",
        )

    if content_type:
        ct_lower = content_type.split(";")[0].strip().lower()
        if not any(ct_lower.startswith(prefix) for prefix in rules["mime_prefixes"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Content-Type '{content_type}' is not allowed for '{category}'",
            )

    if size_bytes is not None and size_bytes > rules["max_bytes"]:
        max_mb = rules["max_bytes"] // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum limit of {max_mb} MB for '{category}'",
        )

    return ext


def generate_object_key(
    event_id: Optional[int],
    category: str,
    filename: str,
    participant_id: Optional[int] = None,
) -> str:
    """Generate a unique event-scoped object key such as events/{event_id}/participant_photos/..."""
    safe_name = sanitize_filename(filename)
    unique_id = uuid.uuid4().hex[:10]
    event_part = str(event_id) if event_id is not None else "global"
    prefix = f"events/{event_part}/{category}"
    if participant_id is not None:
        return f"{prefix}/p{participant_id}_{unique_id}_{safe_name}"
    return f"{prefix}/{unique_id}_{safe_name}"


def build_public_url(
    cfg: Optional[R2Config],
    object_key: str,
    event_id: Optional[int] = None,
) -> str:
    """Resolve the public or retrievable URL for a stored object key."""
    if cfg is not None:
        if cfg.public_url:
            return f"{cfg.public_url.rstrip('/')}/{object_key}"
        # Fallback if bucket has no public domain configured: serve via backend proxy
        eid_q = f"&event_id={event_id}" if event_id is not None else ""
        return f"/api/storage/object?key={object_key}{eid_q}"
    return f"/uploads/{object_key}"


def create_presigned_upload(
    event: Optional[Event],
    category: str,
    filename: str,
    content_type: str,
    participant_id: Optional[int] = None,
    size_bytes: Optional[int] = None,
    expires_in: int = 300,
) -> dict:
    """Generate a presigned upload descriptor (R2 PUT URL or local dev upload endpoint)."""
    validate_upload(category, filename, content_type, size_bytes)
    event_id = event.id if event else None
    object_key = generate_object_key(event_id, category, filename, participant_id=participant_id)
    cfg = resolve_r2_config(event)

    if cfg is not None:
        try:
            client = _get_s3_client(cfg)
            upload_url = client.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": cfg.bucket_name,
                    "Key": object_key,
                    "ContentType": content_type,
                },
                ExpiresIn=expires_in,
            )
        except (BotoCoreError, ClientError) as exc:
            logger.exception("Failed to generate R2 presigned URL for %s", object_key)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Cloudflare R2 presign error: {exc}",
            )

        public_url = build_public_url(cfg, object_key, event_id=event_id)
        return {
            "mode": "r2",
            "upload_url": upload_url,
            "method": "PUT",
            "object_key": object_key,
            "public_url": public_url,
            "headers": {"Content-Type": content_type},
            "expires_in": expires_in,
        }

    # Local filesystem fallback for development
    public_url = build_public_url(None, object_key, event_id=event_id)
    return {
        "mode": "local",
        "upload_url": "/api/storage/local-upload",
        "method": "POST",
        "object_key": object_key,
        "public_url": public_url,
        "headers": {},
        "expires_in": expires_in,
    }


def upload_bytes(
    event: Optional[Event],
    object_key: str,
    data: bytes,
    content_type: str,
) -> tuple[str, str]:
    """Upload raw bytes to R2 (or local filesystem fallback). Returns (public_url, storage_provider)."""
    cfg = resolve_r2_config(event)
    event_id = event.id if event else None

    if cfg is not None:
        try:
            client = _get_s3_client(cfg)
            client.put_object(
                Bucket=cfg.bucket_name,
                Key=object_key,
                Body=data,
                ContentType=content_type,
            )
            public_url = build_public_url(cfg, object_key, event_id=event_id)
            return public_url, "r2"
        except (BotoCoreError, ClientError) as exc:
            logger.exception("Failed to upload bytes to R2 for %s", object_key)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Cloudflare R2 upload error: {exc}",
            )

    # Local filesystem fallback
    local_path = Path(settings.UPLOAD_DIR) / object_key
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(data)
    return build_public_url(None, object_key, event_id=event_id), "local"


def download_bytes(event: Optional[Event], object_key: str) -> Optional[bytes]:
    """Download object bytes from R2 or local filesystem."""
    cfg = resolve_r2_config(event)
    if cfg is not None:
        try:
            client = _get_s3_client(cfg)
            resp = client.get_object(Bucket=cfg.bucket_name, Key=object_key)
            return resp["Body"].read()
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404"):
                logger.warning("R2 object not found: %s", object_key)
                # Fallback to local disk in case it is a legacy local file
            else:
                logger.exception("R2 download error for %s", object_key)
                return None
        except BotoCoreError:
            logger.exception("R2 download BotoCoreError for %s", object_key)
            return None

    # Local fallback (supports both new object_key and legacy uploads/... paths)
    cleaned = object_key.strip().lstrip("/")
    candidates = [
        Path(settings.UPLOAD_DIR) / cleaned,
        Path(cleaned),
    ]
    if cleaned.startswith("uploads/"):
        candidates.append(Path(settings.UPLOAD_DIR) / cleaned[len("uploads/"):])
    for path in candidates:
        if path.exists() and path.is_file():
            return path.read_bytes()
    return None


def delete_object(event: Optional[Event], object_key: str) -> bool:
    """Delete an object from R2 and/or local filesystem. Returns True if deleted without error."""
    if not object_key:
        return False

    deleted = False
    cfg = resolve_r2_config(event)
    if cfg is not None:
        try:
            client = _get_s3_client(cfg)
            client.delete_object(Bucket=cfg.bucket_name, Key=object_key)
            deleted = True
            logger.info("Deleted R2 object: %s", object_key)
        except (BotoCoreError, ClientError):
            logger.warning("Failed to delete R2 object %s", object_key, exc_info=True)

    # Also clean up local file if present
    cleaned = object_key.strip().lstrip("/")
    for path in [Path(settings.UPLOAD_DIR) / cleaned, Path(cleaned)]:
        if path.exists() and path.is_file():
            try:
                path.unlink()
                deleted = True
            except OSError:
                logger.warning("Failed to delete local file %s", path)

    return deleted
