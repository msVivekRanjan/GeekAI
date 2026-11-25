#!/usr/bin/env python3
"""
GeekAI Offline Volunteer Check-In Application
=============================================
Standalone locally-run check-in app supporting:
  - Offline & online Face Recognition (InsightFace)
  - Offline & online QR Code Scanning
  - Offline & online Manual Participant Lookup
  - Session selection (event-level check-in or session-level attendance)
  - Local SQLite persistence & automatic background batch-sync to cloud

Controls:
    Y — Confirm face check-in for matched participant
    N — Reject current face match
    R — Toggle between FACE and QR scanning modes
    C — Change active session
    M — Manual participant lookup (terminal input, offline-capable)
    S — Sync participants/sessions & push pending attendance
    Q — Quit
"""

import logging
import sys
import time
from typing import Optional

import cv2
import numpy as np

from api_client import APIClient
from config import config
from face_detector import DetectedFace, FaceDetector
from local_db import (
    cache_volunteer,
    get_attendance_counts,
    get_cached_volunteer,
    get_sessions,
    has_local_attendance,
    init_db,
    record_attendance_local,
    search_participants as search_local_participants,
)
from matcher import EmbeddingMatcher, MatchResult
from offline_sync import OfflineSyncThread
from qr_scanner import handle_qr_scan
from sync import EmbeddingSync
from ui import CheckInUI, draw_no_match_overlay

# ------------------------------------------------------------------ #
#  Logging                                                            #
# ------------------------------------------------------------------ #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


# ------------------------------------------------------------------ #
#  Application state                                                  #
# ------------------------------------------------------------------ #
class AppState:
    """Mutable state for the main loop."""

    def __init__(self) -> None:
        self.current_match: Optional[MatchResult] = None
        self.pending_confirm = False
        self.last_sync_time = 0.0
        self.running = True
        self.mode = "FACE"  # "FACE" or "QR"
        self.session_id: Optional[int] = None
        self.session_name: str = "Event Check-In (All)"
        self.last_qr_scan_time: float = 0.0


# ------------------------------------------------------------------ #
#  Session selector (terminal-based)                                  #
# ------------------------------------------------------------------ #
def select_session(event_id: int) -> tuple[Optional[int], str]:
    """Prompt the volunteer to select Event Check-In or a specific Session."""
    sessions = get_sessions(event_id)
    if not sessions:
        print("\nNo sessions cached — using Event-Level Check-In (session_id=None).")
        return None, "Event Check-In"

    print("\n=== Select Attendance Target ===")
    print("  0. Event Check-In (General / Gate Entry)")
    for i, s in enumerate(sessions, 1):
        loc = f" @ {s['location']}" if s.get("location") else ""
        print(f"  {i}. {s['name']}{loc}")

    choice = input("Select number [0]: ").strip()
    if not choice or choice == "0":
        return None, "Event Check-In"
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(sessions):
            s = sessions[idx]
            return s["id"], s["name"]
    print("Invalid selection, defaulting to Event Check-In.")
    return None, "Event Check-In"


# ------------------------------------------------------------------ #
#  Manual lookup (offline-first via local SQLite)                     #
# ------------------------------------------------------------------ #
def manual_lookup(event_id: int, session_id: Optional[int]) -> None:
    """Search cached participants in SQLite and record attendance locally."""
    print("\n=== Manual Participant Lookup (Offline-Capable) ===")
    query = input("Enter name, email, or participant ID: ").strip()
    if not query:
        print("Cancelled.")
        return

    results = [
        p for p in search_local_participants(query)
        if p.get("event_id") == event_id
    ]
    if not results:
        print("No matching participants in local cache.")
        return

    print(f"\nFound {len(results)} result(s):")
    for i, p in enumerate(results[:10], 1):
        print(f"  {i}. [{p['id']}] {p['name']} — {p.get('institution') or ''} ({p.get('category') or ''})")

    choice = input("\nSelect number to check in (or Enter to cancel): ").strip()
    if not choice or not choice.isdigit():
        print("Cancelled.")
        return

    idx = int(choice) - 1
    if 0 <= idx < len(results):
        p = results[idx]
        pid = p["id"]
        name = p.get("name", "Unknown")
        if has_local_attendance(pid, session_id):
            print(f"⚠  Attendance already recorded locally for {name}")
            return
        confirm = input(f"Record attendance for {name} (ID {pid})? [y/N]: ").strip().lower()
        if confirm == "y":
            record_attendance_local(
                participant_id=pid,
                event_id=event_id,
                method="MANUAL",
                session_id=session_id,
            )
            print(f"✓  Attendance queued locally for {name}")
        else:
            print("Cancelled.")
    else:
        print("Invalid selection.")


# ------------------------------------------------------------------ #
#  Authentication (online with offline cache fallback)                #
# ------------------------------------------------------------------ #
def authenticate(api: APIClient, event_id: int) -> bool:
    """Authenticate online and cache JWT, or fall back to cached offline token."""
    logger.info("Authenticating with backend at %s …", config.API_URL)
    if api.login():
        cache_volunteer(
            email=config.VOLUNTEER_EMAIL,
            token=api.token or "",
            event_id=event_id,
            volunteer_id=None,
        )
        return True

    cached = get_cached_volunteer(config.VOLUNTEER_EMAIL)
    if cached and cached.get("token"):
        api.token = cached["token"]
        api.session.headers.update({"Authorization": f"Bearer {api.token}"})
        logger.warning("Backend unreachable — authenticated via offline volunteer cache.")
        return True

    return False


# ------------------------------------------------------------------ #
#  Main loop                                                          #
# ------------------------------------------------------------------ #
def main() -> None:
    logger.info("Starting GeekAI Offline Volunteer Check-In")
    init_db()
    event_id = config.EVENT_ID

    # 1. Initialise components
    api = APIClient()
    detector = FaceDetector()
    matcher = EmbeddingMatcher()
    syncer = EmbeddingSync(api, event_id=event_id)
    ui = CheckInUI()
    state = AppState()

    # 2. Authenticate (online or offline cache)
    if not authenticate(api, event_id):
        print(
            "\n✗  Could not authenticate online and no offline volunteer cache found.\n"
            f"   URL:   {config.API_URL}\n"
            f"   Email: {config.VOLUNTEER_EMAIL}\n"
            "   Please connect to the internet for first-time login.\n"
        )
        sys.exit(1)

    # 3. Sync participants, embeddings, and sessions (falls back to SQLite if offline)
    logger.info("Syncing event %d data …", event_id)
    records = syncer.initial_sync()
    loaded = matcher.load_embeddings(records)
    state.last_sync_time = time.time()
    logger.info("Ready — %d participant embeddings loaded", loaded)

    # 4. Select session / mode
    state.session_id, state.session_name = select_session(event_id)

    # 5. Start background offline sync thread
    sync_thread = OfflineSyncThread(api, event_id=event_id)
    sync_thread.start()

    # 6. Load InsightFace model
    logger.info("Loading face detection model '%s' …", config.MODEL_NAME)
    try:
        detector._ensure_loaded()  # noqa: SLF001
    except RuntimeError as exc:
        logger.error(str(exc))
        print(f"\n✗  {exc}\n")
        sync_thread.stop()
        sys.exit(1)

    # 7. Open webcam
    logger.info("Opening camera %d …", config.CAMERA_INDEX)
    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    if not cap.isOpened():
        logger.error("Cannot open camera index %d", config.CAMERA_INDEX)
        print(f"\n✗  Cannot open camera (index {config.CAMERA_INDEX}).\n")
        sync_thread.stop()
        sys.exit(1)

    # 8. Init UI
    ui.init_window()
    counts = get_attendance_counts()
    ui.set_connection_info(
        connected=sync_thread.is_online,
        embeddings=matcher.count,
        last_sync=time.strftime("%H:%M:%S", time.localtime(state.last_sync_time)),
        pending_count=counts.get("PENDING", 0) + counts.get("FAILED", 0),
    )
    ui.set_session_info(state.session_name, state.mode)
    ui.set_status("Ready — point camera at participant", (0, 200, 0))

    logger.info("Entering main loop. Press Q to quit.")

    try:
        while state.running:
            ret, frame = cap.read()
            if not ret:
                ui.set_status("Camera error — no frame", (0, 0, 220))
                blank = np.zeros((ui.height, ui.width, 3), dtype=np.uint8)
                key = ui.show(blank)
                if key == ord("q"):
                    break
                continue

            # Update sync & pending indicator
            ui.set_sync_status(sync_thread.is_online, sync_thread.pending_count)

            faces: list[DetectedFace] = []
            if state.mode == "FACE":
                try:
                    faces = detector.detect_faces(frame)
                except Exception as exc:
                    logger.warning("Detection error: %s", exc)

                if faces and not state.pending_confirm:
                    best_face = max(faces, key=lambda f: f.score)
                    match = matcher.find_match(best_face.embedding)
                    if match:
                        state.current_match = match
                        state.pending_confirm = True
                        ui.set_status(f"Match: {match.name} ({match.similarity:.0%})", (0, 220, 220))
                        api.download_photo(match.participant_id, match.photo_url)
                    else:
                        state.current_match = None
            else:
                # QR mode
                if time.time() - state.last_qr_scan_time > 2.0:
                    participant, msg = handle_qr_scan(
                        frame,
                        event_id=event_id,
                        session_id=state.session_id,
                    )
                    if msg:
                        state.last_qr_scan_time = time.time()
                        col = (0, 200, 0) if participant and msg.startswith("✓") else (0, 220, 220)
                        ui.flash(msg, col, duration=2.5)
                        ui.set_status(msg, col)

            canvas = ui.render_frame(
                frame,
                faces=faces,
                match=state.current_match,
                pending_confirm=state.pending_confirm,
            )

            if state.mode == "FACE" and not faces:
                draw_no_match_overlay(canvas)
                ui.set_status("No face detected", (0, 0, 220))

            key = ui.show(canvas)

            # ---- Key handling ---- #
            if key == ord("q"):
                state.running = False

            elif key == ord("y") and state.pending_confirm and state.current_match:
                pid = state.current_match.participant_id
                name = state.current_match.name
                if has_local_attendance(pid, state.session_id):
                    ui.flash(f"Already checked in: {name}", (0, 220, 220))
                else:
                    record_attendance_local(
                        participant_id=pid,
                        event_id=event_id,
                        method="FACE",
                        session_id=state.session_id,
                    )
                    ui.flash(f"Checked in: {name}", (0, 200, 0))
                    logger.info("Local FACE check-in: %s (ID %d)", name, pid)
                state.current_match = None
                state.pending_confirm = False
                ui.set_status("Ready — point camera at participant", (0, 200, 0))

            elif key == ord("n") and state.pending_confirm:
                ui.flash("Match rejected", (0, 0, 220), duration=1.5)
                state.current_match = None
                state.pending_confirm = False
                ui.set_status("Ready — point camera at participant", (0, 200, 0))

            elif key == ord("r"):
                state.mode = "QR" if state.mode == "FACE" else "FACE"
                state.current_match = None
                state.pending_confirm = False
                ui.set_session_info(state.session_name, state.mode)
                ui.flash(f"Switched to {state.mode} mode", (0, 220, 220), duration=1.5)

            elif key == ord("c"):
                state.current_match = None
                state.pending_confirm = False
                state.session_id, state.session_name = select_session(event_id)
                ui.set_session_info(state.session_name, state.mode)
                ui.flash(f"Session: {state.session_name}", (0, 220, 220), duration=2.0)

            elif key == ord("m"):
                state.pending_confirm = False
                state.current_match = None
                manual_lookup(event_id, state.session_id)
                ui.set_status("Ready — point camera at participant", (0, 200, 0))

            elif key == ord("s"):
                ui.set_status("Syncing …", (0, 220, 220))
                ui.flash("Syncing …", (0, 220, 220), duration=1.0)
                sync_thread.trigger_sync()
                records = syncer.refresh()
                loaded = matcher.load_embeddings(records)
                state.last_sync_time = time.time()
                ui.set_connection_info(
                    connected=sync_thread.is_online,
                    embeddings=matcher.count,
                    last_sync=time.strftime("%H:%M:%S", time.localtime(state.last_sync_time)),
                    pending_count=sync_thread.pending_count,
                )
                ui.set_status("Ready — point camera at participant", (0, 200, 0))
                ui.flash(f"Synced — {loaded} faces loaded", (0, 200, 0))

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        sync_thread.stop()
        cap.release()
        ui.destroy()
        logger.info("Shut down cleanly")


if __name__ == "__main__":
    main()
