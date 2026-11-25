"""QR code generation service with Cloudflare R2 and local fallback support."""

from __future__ import annotations

import io
import json
import logging
from typing import Optional

import qrcode
from qrcode.image.pil import PilImage

from app.core.config import settings
from app.models.models import Event
from app.services import storage_service

logger = logging.getLogger(__name__)


def _build_qr_bytes(participant_id: int, name: str) -> bytes:
    """Render a participant QR code PNG into an in-memory bytes buffer."""
    data = json.dumps({"participant_id": participant_id, "name": name})
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img: PilImage = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_qr_code(participant_id: int, name: str) -> str:
    """Legacy local QR generator (kept for backward compatibility)."""
    qr_bytes = _build_qr_bytes(participant_id, name)
    out_dir = settings.qrcodes_dir
    filename = f"{participant_id}.png"
    filepath = out_dir / filename
    filepath.write_bytes(qr_bytes)
    logger.info("QR code saved to %s", filepath)
    return f"uploads/qrcodes/{filename}"


def generate_qr_code_for_event(
    participant_id: int,
    name: str,
    event: Optional[Event],
) -> tuple[str, str, bytes, str]:
    """Generate QR code PNG bytes and store in R2 (or local fallback).

    Returns (public_url, object_key, qr_bytes, storage_provider).
    """
    qr_bytes = _build_qr_bytes(participant_id, name)
    event_id = event.id if event else None
    object_key = storage_service.generate_object_key(
        event_id=event_id,
        category="qr_codes",
        filename=f"{participant_id}.png",
        participant_id=participant_id,
    )
    public_url, provider = storage_service.upload_bytes(
        event=event,
        object_key=object_key,
        data=qr_bytes,
        content_type="image/png",
    )
    logger.info("QR code stored (%s): %s", provider, object_key)
    return public_url, object_key, qr_bytes, provider
