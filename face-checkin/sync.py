"""
Embedding synchronisation and local caching.
Downloads face embeddings from the backend and persists them to disk.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config import config
from local_db import (
    get_all_participants,
    init_db,
    update_participant_photo_local,
    upsert_participants,
    upsert_sessions,
)

logger = logging.getLogger(__name__)


class EmbeddingSync:
    """Download, cache, and refresh participant face embeddings, photos, and sessions."""

    def __init__(self, api_client: Any, event_id: Optional[int] = None) -> None:
        """
        Args:
            api_client: An initialised APIClient instance.
            event_id: Event ID to sync participants and sessions for.
        """
        self.api = api_client
        self.event_id = event_id or config.EVENT_ID
        self._cache_file = config.embeddings_cache_file()
        self._last_sync: Optional[str] = None  # ISO timestamp of last sync
        self._records: list[dict] = []
        init_db()

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def initial_sync(self) -> list[dict]:
        """Perform a full sync: load SQLite/disk cache, then fetch updates from backend.

        Returns the full list of embedding records for EmbeddingMatcher.
        """
        # 1. Load whatever is cached locally first (works 100% offline)
        self._load_sqlite_records()
        if not self._records:
            self._load_cache()

        # 2. Fetch participants & sessions from offline-sync API if online
        self._sync_from_backend()

        logger.info("Sync complete: %d total embeddings ready", len(self._records))
        return self._records

    def refresh(self) -> list[dict]:
        """Incremental/manual sync — fetch participants & sessions from backend."""
        self._sync_from_backend()
        return self._records

    def _sync_from_backend(self) -> None:
        """Download participants + embeddings and sessions into SQLite."""
        try:
            participants = self.api.download_participants(self.event_id)
            if participants:
                upsert_participants(participants)
                self._download_photos(
                    [{"participant_id": p["id"], "photo_url": p.get("photo_url")} for p in participants]
                )
                self._load_sqlite_records()
                self._save_cache()
                logger.info("Synced %d participants to SQLite", len(participants))

            sessions = self.api.download_sessions(self.event_id)
            if sessions:
                upsert_sessions(sessions)
                logger.info("Synced %d sessions to SQLite", len(sessions))
        except Exception as exc:
            logger.warning("Backend sync skipped (offline?): %s", exc)

    def _load_sqlite_records(self) -> None:
        """Load embedding records from local SQLite into matcher format."""
        rows = get_all_participants(self.event_id)
        records = []
        for r in rows:
            emb_raw = r.get("embedding")
            emb = None
            if emb_raw:
                try:
                    emb = json.loads(emb_raw) if isinstance(emb_raw, str) else emb_raw
                except Exception:
                    emb = None
            if emb:
                records.append({
                    "participant_id": r["id"],
                    "name": r.get("name", "Unknown"),
                    "embedding": emb,
                    "photo_url": r.get("photo_url"),
                    "institution": r.get("institution"),
                    "category": r.get("category"),
                })
        if records:
            self._records = records

    @property
    def records(self) -> list[dict]:
        return self._records

    @property
    def last_sync_time(self) -> Optional[str]:
        return self._last_sync

    # ------------------------------------------------------------------ #
    #  Cache persistence                                                  #
    # ------------------------------------------------------------------ #

    def _load_cache(self) -> None:
        if not self._cache_file.exists():
            logger.info("No embedding cache found — starting fresh")
            return
        try:
            with open(self._cache_file, "r") as f:
                data = json.load(f)
            self._records = data.get("records", [])
            self._last_sync = data.get("last_sync")
            logger.info(
                "Loaded %d cached embeddings (last sync: %s)",
                len(self._records),
                self._last_sync,
            )
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load cache, starting fresh: %s", exc)
            self._records = []
            self._last_sync = None

    def _save_cache(self) -> None:
        self._last_sync = datetime.now(timezone.utc).isoformat()
        payload = {
            "last_sync": self._last_sync,
            "records": self._records,
        }
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cache_file, "w") as f:
                json.dump(payload, f)
            logger.debug("Cache saved (%d records)", len(self._records))
        except OSError as exc:
            logger.error("Failed to save cache: %s", exc)

    # ------------------------------------------------------------------ #
    #  Merge logic                                                        #
    # ------------------------------------------------------------------ #

    def _merge_records(self, new_records: list[dict]) -> None:
        """Merge new records into the existing set, replacing duplicates by participant_id."""
        existing_map = {r["participant_id"]: r for r in self._records}
        for rec in new_records:
            existing_map[rec["participant_id"]] = rec
        self._records = list(existing_map.values())

    # ------------------------------------------------------------------ #
    #  Photo prefetch                                                     #
    # ------------------------------------------------------------------ #

    def _download_photos(self, records: list[dict]) -> None:
        """Download photos for the given records and update SQLite photo_local."""
        for rec in records:
            try:
                pid = rec["participant_id"]
                dest = self.api.download_photo(pid, rec.get("photo_url"))
                if dest is not None:
                    update_participant_photo_local(pid, str(dest))
            except Exception as exc:
                logger.debug(
                    "Photo download failed for participant %s: %s",
                    rec.get("participant_id"),
                    exc,
                )
