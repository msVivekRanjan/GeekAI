"""
SQLite local database for the offline volunteer app.
Stores participants, sessions, attendance queue, and volunteer auth cache.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from config import config

logger = logging.getLogger(__name__)

_DB_PATH: Path = config.sqlite_db_path() if hasattr(config, "sqlite_db_path") else config.cache_path() / "offline.db"


def _get_conn() -> sqlite3.Connection:
    """Return a SQLite connection with row_factory set for dict-like access."""
    conn = sqlite3.connect(str(_DB_PATH), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create all tables if they don't exist."""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS participants (
                id          INTEGER PRIMARY KEY,
                name        TEXT    NOT NULL,
                email       TEXT,
                phone       TEXT,
                institution TEXT,
                category    TEXT,
                photo_url   TEXT,
                photo_local TEXT,
                qr_code     TEXT,
                event_id    INTEGER NOT NULL,
                embedding   TEXT,  -- JSON array of floats
                cached_at   TEXT   NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id         INTEGER PRIMARY KEY,
                name       TEXT    NOT NULL,
                event_id   INTEGER NOT NULL,
                start_time TEXT,
                end_time   TEXT,
                location   TEXT,
                cached_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS attendance_queue (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                local_uuid      TEXT    NOT NULL UNIQUE,
                participant_id  INTEGER NOT NULL,
                session_id      INTEGER,
                method          TEXT    NOT NULL,
                marked_at       TEXT    NOT NULL,
                event_id        INTEGER NOT NULL,
                volunteer_id    INTEGER,
                sync_status     TEXT    NOT NULL DEFAULT 'PENDING',
                sync_attempts   INTEGER NOT NULL DEFAULT 0,
                error_message   TEXT,
                synced_at       TEXT
            );

            CREATE TABLE IF NOT EXISTS volunteer_cache (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                email        TEXT    NOT NULL UNIQUE,
                token        TEXT    NOT NULL,
                token_expiry TEXT,
                event_id     INTEGER,
                volunteer_id INTEGER,
                cached_at    TEXT    NOT NULL
            );
        """)
    logger.info("Local SQLite DB initialized at %s", _DB_PATH)


# ---------------------------------------------------------------------------
# Participants
# ---------------------------------------------------------------------------

def upsert_participants(participants: list[dict]) -> int:
    """Insert or replace participants in the local DB. Returns count upserted."""
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO participants
                (id, name, email, phone, institution, category, photo_url,
                 qr_code, event_id, embedding, cached_at)
            VALUES
                (:id, :name, :email, :phone, :institution, :category, :photo_url,
                 :qr_code, :event_id, :embedding, :cached_at)
            """,
            [
                {
                    "id": p["id"],
                    "name": p.get("name", ""),
                    "email": p.get("email"),
                    "phone": p.get("phone"),
                    "institution": p.get("institution"),
                    "category": p.get("category"),
                    "photo_url": p.get("photo_url"),
                    "qr_code": p.get("qr_code"),
                    "event_id": p.get("event_id"),
                    "embedding": json.dumps(p["embedding"]) if p.get("embedding") is not None else None,
                    "cached_at": now,
                }
                for p in participants
            ],
        )
    return len(participants)


def get_all_participants(event_id: Optional[int] = None) -> list[dict]:
    with _get_conn() as conn:
        if event_id:
            rows = conn.execute(
                "SELECT * FROM participants WHERE event_id = ?", (event_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM participants").fetchall()
    return [dict(r) for r in rows]


def find_participant_by_id(pid: int) -> Optional[dict]:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM participants WHERE id = ?", (pid,)).fetchone()
    return dict(row) if row else None


def search_participants(query: str) -> list[dict]:
    q = f"%{query}%"
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM participants WHERE name LIKE ? OR email LIKE ? OR id = ?",
            (q, q, query if query.isdigit() else -1),
        ).fetchall()
    return [dict(r) for r in rows]


def update_participant_photo_local(pid: int, local_path: str) -> None:
    with _get_conn() as conn:
        conn.execute(
            "UPDATE participants SET photo_local = ? WHERE id = ?", (local_path, pid)
        )


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def upsert_sessions(sessions: list[dict]) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO sessions
                (id, name, event_id, start_time, end_time, location, cached_at)
            VALUES
                (:id, :name, :event_id, :start_time, :end_time, :location, :cached_at)
            """,
            [
                {
                    "id": s["id"],
                    "name": s.get("name", ""),
                    "event_id": s.get("event_id"),
                    "start_time": s.get("start_time"),
                    "end_time": s.get("end_time"),
                    "location": s.get("location"),
                    "cached_at": now,
                }
                for s in sessions
            ],
        )
    return len(sessions)


def get_sessions(event_id: Optional[int] = None) -> list[dict]:
    with _get_conn() as conn:
        if event_id:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE event_id = ? ORDER BY start_time", (event_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM sessions ORDER BY start_time").fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Attendance Queue
# ---------------------------------------------------------------------------

def record_attendance_local(
    participant_id: int,
    event_id: int,
    method: str,
    session_id: Optional[int] = None,
    volunteer_id: Optional[int] = None,
    marked_at: Optional[str] = None,
) -> str:
    """Record an attendance event locally. Returns the local_uuid."""
    local_uuid = str(uuid4())
    now = marked_at or datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO attendance_queue
                (local_uuid, participant_id, session_id, method, marked_at,
                 event_id, volunteer_id, sync_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING')
            """,
            (local_uuid, participant_id, session_id, method, now, event_id, volunteer_id),
        )
    logger.info(
        "Local attendance recorded: participant=%d session=%s method=%s uuid=%s",
        participant_id, session_id, method, local_uuid,
    )
    return local_uuid


def get_pending_attendance(limit: int = 50) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM attendance_queue WHERE sync_status = 'PENDING' ORDER BY marked_at LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_attendance_synced(local_uuid: str, attendance_id: Optional[int] = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.execute(
            """
            UPDATE attendance_queue
            SET sync_status = 'SYNCED', synced_at = ?, error_message = NULL
            WHERE local_uuid = ?
            """,
            (now, local_uuid),
        )


def mark_attendance_failed(local_uuid: str, error: str) -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            UPDATE attendance_queue
            SET sync_status = 'FAILED',
                sync_attempts = sync_attempts + 1,
                error_message = ?
            WHERE local_uuid = ?
            """,
            (error, local_uuid),
        )


def reset_failed_attendance() -> int:
    """Reset FAILED records back to PENDING for retry."""
    with _get_conn() as conn:
        cur = conn.execute(
            "UPDATE attendance_queue SET sync_status = 'PENDING' WHERE sync_status = 'FAILED'"
        )
    return cur.rowcount


def get_attendance_counts() -> dict:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT sync_status, COUNT(*) as cnt FROM attendance_queue GROUP BY sync_status"
        ).fetchall()
    return {r["sync_status"]: r["cnt"] for r in rows}


def has_local_attendance(participant_id: int, session_id: Optional[int] = None) -> bool:
    """Check if attendance already recorded locally (avoid double-tapping)."""
    with _get_conn() as conn:
        if session_id is None:
            row = conn.execute(
                "SELECT id FROM attendance_queue WHERE participant_id = ? AND session_id IS NULL LIMIT 1",
                (participant_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id FROM attendance_queue WHERE participant_id = ? AND session_id = ? LIMIT 1",
                (participant_id, session_id),
            ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Volunteer cache
# ---------------------------------------------------------------------------

def cache_volunteer(email: str, token: str, event_id: Optional[int], volunteer_id: Optional[int], token_expiry: Optional[str] = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO volunteer_cache
                (email, token, token_expiry, event_id, volunteer_id, cached_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (email, token, token_expiry, event_id, volunteer_id, now),
        )


def get_cached_volunteer(email: str) -> Optional[dict]:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM volunteer_cache WHERE email = ?", (email,)
        ).fetchone()
    return dict(row) if row else None


def clear_volunteer_cache(email: str) -> None:
    with _get_conn() as conn:
        conn.execute("DELETE FROM volunteer_cache WHERE email = ?", (email,))
