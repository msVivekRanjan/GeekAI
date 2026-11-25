"""
HTTP client for communicating with the GeekAI backend API.
Handles authentication, embedding sync, attendance recording, and participant lookup.
"""

import logging
import time
from pathlib import Path
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import config

logger = logging.getLogger(__name__)


class APIClient:
    """HTTP client for the GeekAI backend."""

    def __init__(self) -> None:
        self.base_url = config.API_URL.rstrip("/")
        self.token: Optional[str] = None
        self.session = self._build_session()

    # ------------------------------------------------------------------ #
    #  Session with retry policy                                          #
    # ------------------------------------------------------------------ #

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=config.API_RETRIES,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({"Content-Type": "application/json"})
        return session

    # ------------------------------------------------------------------ #
    #  Auth helpers                                                       #
    # ------------------------------------------------------------------ #

    def _auth_headers(self) -> dict[str, str]:
        if not self.token:
            raise RuntimeError("Not authenticated — call login() first.")
        return {"Authorization": f"Bearer {self.token}"}

    def login(self, email: Optional[str] = None, password: Optional[str] = None) -> bool:
        """Authenticate with the backend and store the JWT token."""
        email = email or config.VOLUNTEER_EMAIL
        password = password or config.VOLUNTEER_PASSWORD
        url = f"{self.base_url}/api/auth/login"
        try:
            resp = self.session.post(
                url,
                json={"email": email, "password": password},
                timeout=config.API_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            self.token = data.get("access_token")
            if not self.token:
                logger.error("Login response missing access_token: %s", data)
                return False
            self.session.headers.update(self._auth_headers())
            logger.info("Logged in as %s", email)
            return True
        except requests.RequestException as exc:
            logger.error("Login failed: %s", exc)
            return False

    # ------------------------------------------------------------------ #
    #  Embeddings                                                         #
    # ------------------------------------------------------------------ #

    def sync_embeddings(self, since: Optional[str] = None) -> list[dict[str, Any]]:
        """Download participant embeddings from the backend.

        Returns a list of dicts:
          [{participant_id, name, embedding: [512 floats], photo_url}, ...]
        """
        url = f"{self.base_url}/api/embeddings/sync"
        params: dict[str, str] = {}
        if since:
            params["since"] = since
        try:
            resp = self.session.get(url, params=params, timeout=config.API_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            logger.info("Synced %d embeddings", len(data))
            return data
        except requests.RequestException as exc:
            logger.error("Embedding sync failed: %s", exc)
            return []

    # ------------------------------------------------------------------ #
    #  Attendance                                                         #
    # ------------------------------------------------------------------ #

    def record_attendance(self, participant_id: int, method: str = "FACE") -> dict[str, Any]:
        """Record event-level attendance for a participant.

        Returns the API response dict on success, or an error dict.
        """
        url = f"{self.base_url}/api/attendance/"
        payload = {
            "participant_id": participant_id,
            "session_id": None,
            "method": method,
        }
        try:
            resp = self.session.post(url, json=payload, timeout=config.API_TIMEOUT)
            if resp.status_code == 409:
                return {"status": "duplicate", "message": "Attendance already recorded"}
            resp.raise_for_status()
            logger.info("Attendance recorded for participant %d", participant_id)
            return resp.json()
        except requests.RequestException as exc:
            logger.error("Failed to record attendance: %s", exc)
            return {"status": "error", "message": str(exc)}

    # ------------------------------------------------------------------ #
    #  Participants                                                       #
    # ------------------------------------------------------------------ #

    def search_participants(self, query: str) -> list[dict[str, Any]]:
        """Search participants by name or ID."""
        url = f"{self.base_url}/api/participants/"
        try:
            resp = self.session.get(
                url,
                params={"search": query},
                timeout=config.API_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict):
                return data.get("items", [])
            return data
        except requests.RequestException as exc:
            logger.error("Participant search failed: %s", exc)
            return []

    def get_participant(self, participant_id: int) -> Optional[dict[str, Any]]:
        """Get details for a single participant."""
        url = f"{self.base_url}/api/participants/{participant_id}"
        try:
            resp = self.session.get(url, timeout=config.API_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.error("Get participant %d failed: %s", participant_id, exc)
            return None

    # ------------------------------------------------------------------ #
    #  Photo download                                                     #
    # ------------------------------------------------------------------ #

    def download_photo(self, participant_id: int, photo_url: Optional[str] = None) -> Optional[Path]:
        """Download and cache a participant's photo locally.

        Returns the local file path on success, None on failure.
        """
        dest = config.photos_path() / f"{participant_id}.jpg"
        if dest.exists():
            return dest

        if photo_url:
            # If photo_url is relative, prepend base URL
            if photo_url.startswith("/"):
                url = f"{self.base_url}{photo_url}"
            elif photo_url.startswith("http"):
                url = photo_url
            else:
                url = f"{self.base_url}/{photo_url}"
        else:
            url = f"{self.base_url}/uploads/photos/{participant_id}.jpg"

        try:
            resp = self.session.get(url, timeout=config.API_TIMEOUT, stream=True)
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.debug("Downloaded photo for participant %d", participant_id)
            return dest
        except requests.RequestException as exc:
            logger.debug("Photo download failed for participant %d: %s", participant_id, exc)
            return None

    # ------------------------------------------------------------------ #
    #  Offline Sync                                                       #
    # ------------------------------------------------------------------ #

    def health_check(self) -> bool:
        """Ping the backend health endpoint. Returns True if online."""
        try:
            resp = self.session.get(
                f"{self.base_url}/api/offline/health",
                timeout=5,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def download_participants(self, event_id: int) -> list[dict[str, Any]]:
        """Download all confirmed participants + embeddings for the event."""
        url = f"{self.base_url}/api/offline/participants"
        try:
            resp = self.session.get(url, params={"event_id": event_id}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data.get("participants", [])
        except requests.RequestException as exc:
            logger.error("Failed to download participants: %s", exc)
            return []

    def download_sessions(self, event_id: int) -> list[dict[str, Any]]:
        """Download sessions for the event."""
        url = f"{self.base_url}/api/offline/sessions"
        try:
            resp = self.session.get(url, params={"event_id": event_id}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            return data.get("sessions", [])
        except requests.RequestException as exc:
            logger.error("Failed to download sessions: %s", exc)
            return []

    def sync_attendance_batch(self, records: list[dict], event_id: int) -> Optional[dict[str, Any]]:
        """Submit a batch of offline attendance records for sync.

        Returns the response dict on success, None on network failure.
        """
        url = f"{self.base_url}/api/offline/sync/attendance"
        payload = {"records": records}
        try:
            resp = self.session.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.ConnectionError:
            logger.warning("Offline sync: network unavailable")
            return None
        except requests.RequestException as exc:
            logger.error("Offline sync failed: %s", exc)
            return None
