"""
QR code scanning module for the offline volunteer app.
Decodes QR codes from webcam frames, looks up participants locally,
and records attendance in the local SQLite queue.
"""

import logging
from typing import Optional, Tuple

import cv2
import numpy as np

from config import config
from local_db import (
    find_participant_by_id,
    has_local_attendance,
    record_attendance_local,
    search_participants,
)

logger = logging.getLogger(__name__)


def decode_qr_from_frame(frame: np.ndarray) -> Optional[str]:
    """Decode a QR code from a BGR OpenCV frame.

    Returns the decoded string, or None if no QR found.
    Uses OpenCV's built-in QRCodeDetector (no extra deps needed).
    Falls back to pyzbar if available.
    """
    # Try OpenCV built-in first
    detector = cv2.QRCodeDetector()
    data, _, _ = detector.detectAndDecode(frame)
    if data:
        return data.strip()

    # Try pyzbar fallback
    try:
        from pyzbar import pyzbar
        barcodes = pyzbar.decode(frame)
        for barcode in barcodes:
            if barcode.type == "QRCODE":
                return barcode.data.decode("utf-8").strip()
    except ImportError:
        pass

    return None


def parse_participant_id_from_qr(qr_data: str) -> Optional[int]:
    """Extract the participant ID from a QR code payload.

    Supports formats:
      - Plain integer: "123"
      - URL with /success?id=123 or /success/123
      - JSON: {"participant_id": 123, ...}
      - Prefixed: "GEEKAI:123"
    """
    if not qr_data:
        return None

    # Plain integer
    if qr_data.isdigit():
        return int(qr_data)

    # Prefixed "GEEKAI:123" or "ID:123"
    if ":" in qr_data:
        parts = qr_data.split(":", 1)
        if parts[-1].strip().isdigit():
            return int(parts[-1].strip())

    # URL-based: extract ?id= or last path segment
    if "/" in qr_data or "?" in qr_data:
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(qr_data)
            # ?id=123 or ?participant_id=123
            qs = parse_qs(parsed.query)
            for key in ("id", "participant_id", "pid"):
                if key in qs and qs[key][0].isdigit():
                    return int(qs[key][0])
            # Last path segment
            segments = [s for s in parsed.path.split("/") if s]
            if segments and segments[-1].isdigit():
                return int(segments[-1])
        except Exception:
            pass

    # JSON
    if qr_data.startswith("{"):
        try:
            import json
            data = json.loads(qr_data)
            for key in ("participant_id", "id", "pid"):
                if key in data and str(data[key]).isdigit():
                    return int(data[key])
        except Exception:
            pass

    return None


def handle_qr_scan(
    frame: np.ndarray,
    event_id: int,
    session_id: Optional[int] = None,
    volunteer_id: Optional[int] = None,
) -> Tuple[Optional[dict], str]:
    """
    Scan a QR code from the frame, look up the participant locally,
    and record attendance.

    Returns:
        (participant_dict, status_message)
        participant_dict is None if scan fails or participant not found.
        status_message is a human-readable result.
    """
    qr_data = decode_qr_from_frame(frame)
    if not qr_data:
        return None, ""

    pid = parse_participant_id_from_qr(qr_data)
    if pid is None:
        logger.warning("Could not extract participant ID from QR: %s", qr_data)
        return None, f"Invalid QR code: {qr_data[:40]}"

    participant = find_participant_by_id(pid)
    if not participant:
        logger.warning("Participant %d not found in local cache", pid)
        return None, f"Participant #{pid} not found in local cache"

    if participant.get("event_id") != event_id:
        return None, f"Participant #{pid} belongs to a different event"

    # Check for duplicate
    if has_local_attendance(pid, session_id):
        return participant, f"Already checked in: {participant['name']}"

    # Record locally
    record_attendance_local(
        participant_id=pid,
        event_id=event_id,
        method="QR",
        session_id=session_id,
        volunteer_id=volunteer_id,
    )
    return participant, f"✓ Checked in: {participant['name']}"
