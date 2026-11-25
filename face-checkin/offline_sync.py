"""
Background sync thread for the offline volunteer app.
Reads PENDING records from local SQLite and syncs them to the cloud backend.
Runs every SYNC_INTERVAL seconds in a daemon thread.
"""

import logging
import threading
import time
from typing import Optional
from uuid import UUID

from config import config
from local_db import (
    get_pending_attendance,
    get_attendance_counts,
    mark_attendance_synced,
    mark_attendance_failed,
    reset_failed_attendance,
)

logger = logging.getLogger(__name__)


class OfflineSyncThread(threading.Thread):
    """Background thread that periodically syncs pending attendance to the cloud."""

    def __init__(self, api_client, event_id: int) -> None:
        super().__init__(daemon=True, name="offline-sync")
        self.api = api_client
        self.event_id = event_id
        self._stop_event = threading.Event()
        self._online = False
        self._last_sync_time: Optional[float] = None
        self._pending_count: int = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    #  Public interface                                                   #
    # ------------------------------------------------------------------ #

    @property
    def is_online(self) -> bool:
        with self._lock:
            return self._online

    @property
    def pending_count(self) -> int:
        with self._lock:
            return self._pending_count

    def stop(self) -> None:
        self._stop_event.set()

    def trigger_sync(self) -> None:
        """Trigger an immediate sync (called from main thread on reconnect)."""
        self._sync_now()

    # ------------------------------------------------------------------ #
    #  Thread main loop                                                   #
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        logger.info("Offline sync thread started (interval=%ds)", config.SYNC_INTERVAL)
        while not self._stop_event.is_set():
            self._check_connectivity()
            if self._online:
                self._sync_now()
            self._update_pending_count()
            self._stop_event.wait(timeout=config.SYNC_INTERVAL)

    # ------------------------------------------------------------------ #
    #  Connectivity check                                                 #
    # ------------------------------------------------------------------ #

    def _check_connectivity(self) -> None:
        try:
            result = self.api.health_check()
            with self._lock:
                self._online = result
        except Exception:
            with self._lock:
                self._online = False

    # ------------------------------------------------------------------ #
    #  Sync logic                                                         #
    # ------------------------------------------------------------------ #

    def _sync_now(self) -> None:
        """Sync up to 100 pending records in one batch call."""
        # Reset failed records for retry (after some attempts)
        reset_failed_attendance()

        pending = get_pending_attendance(limit=100)
        if not pending:
            logger.debug("No pending records to sync")
            return

        logger.info("Syncing %d pending attendance records…", len(pending))

        # Build batch payload
        records = []
        for row in pending:
            records.append({
                "local_uuid": row["local_uuid"],
                "participant_id": row["participant_id"],
                "session_id": row["session_id"],
                "method": row["method"],
                "marked_at": row["marked_at"],
                "event_id": row["event_id"],
            })

        try:
            response = self.api.sync_attendance_batch(records, self.event_id)
            if response is None:
                logger.warning("Sync returned None — backend may be offline")
                return

            # Process per-record results
            results = response.get("results", [])
            synced_count = 0
            for result in results:
                local_uuid = result.get("local_uuid")
                status = result.get("status")
                if status in ("synced", "already_synced", "duplicate"):
                    mark_attendance_synced(local_uuid)
                    synced_count += 1
                elif status == "error":
                    mark_attendance_failed(local_uuid, result.get("message", "unknown error"))
                    logger.warning("Sync error for %s: %s", local_uuid, result.get("message"))

            self._last_sync_time = time.time()
            logger.info("Sync complete: %d synced, %d total", synced_count, len(results))

        except Exception as exc:
            logger.error("Sync batch failed: %s", exc)
            # Mark all as failed
            for row in pending:
                mark_attendance_failed(row["local_uuid"], str(exc))

    def _update_pending_count(self) -> None:
        try:
            counts = get_attendance_counts()
            with self._lock:
                self._pending_count = counts.get("PENDING", 0) + counts.get("FAILED", 0)
        except Exception:
            pass
