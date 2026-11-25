"""
OpenCV-based UI for the Face Check-in application.
Displays the webcam feed, overlays match information, and handles keyboard input.
"""

import logging
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from config import config
from matcher import MatchResult

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
#  Colour palette                                                     #
# ------------------------------------------------------------------ #
COL_GREEN = (0, 200, 0)
COL_RED = (0, 0, 220)
COL_YELLOW = (0, 220, 220)
COL_WHITE = (255, 255, 255)
COL_BLACK = (0, 0, 0)
COL_DARK_BG = (40, 40, 40)
COL_PANEL_BG = (30, 30, 30)
COL_ACCENT = (255, 160, 0)  # orange-ish


class CheckInUI:
    """Manages the OpenCV display window and renders overlays."""

    WINDOW_NAME = "GeekAI Face Check-In"

    def __init__(self) -> None:
        self.width = config.WINDOW_WIDTH
        self.height = config.WINDOW_HEIGHT
        self._status_msg = "Initialising…"
        self._status_color = COL_YELLOW
        self._flash_msg: Optional[str] = None
        self._flash_color = COL_GREEN
        self._flash_until = 0.0
        self._embeddings_count = 0
        self._last_sync_display = "never"
        self._connected = False
        self._pending_sync_count = 0
        self._session_name = "Event Check-In"
        self._mode = "FACE"

    # ------------------------------------------------------------------ #
    #  Window lifecycle                                                   #
    # ------------------------------------------------------------------ #

    def init_window(self) -> None:
        cv2.namedWindow(self.WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.WINDOW_NAME, self.width, self.height)

    def destroy(self) -> None:
        cv2.destroyAllWindows()

    # ------------------------------------------------------------------ #
    #  Status helpers                                                     #
    # ------------------------------------------------------------------ #

    def set_status(self, msg: str, color: tuple = COL_WHITE) -> None:
        self._status_msg = msg
        self._status_color = color

    def set_connection_info(
        self,
        connected: bool,
        embeddings: int,
        last_sync: str,
        pending_count: Optional[int] = None,
    ) -> None:
        self._connected = connected
        self._embeddings_count = embeddings
        self._last_sync_display = last_sync
        if pending_count is not None:
            self._pending_sync_count = pending_count

    def set_sync_status(self, online: bool, pending_count: int) -> None:
        self._connected = online
        self._pending_sync_count = pending_count

    def set_session_info(self, session_name: str, mode: str) -> None:
        self._session_name = session_name
        self._mode = mode

    def flash(self, msg: str, color: tuple = COL_GREEN, duration: float = 3.0) -> None:
        """Show a temporary message overlay."""
        self._flash_msg = msg
        self._flash_color = color
        self._flash_until = time.time() + duration

    # ------------------------------------------------------------------ #
    #  Main render                                                        #
    # ------------------------------------------------------------------ #

    def render_frame(
        self,
        frame: np.ndarray,
        faces: list | None = None,
        match: Optional[MatchResult] = None,
        pending_confirm: bool = False,
    ) -> np.ndarray:
        """Compose the full display frame and return it.

        Args:
            frame: Raw BGR webcam frame.
            faces: List of DetectedFace objects to draw bounding boxes for.
            match: Current best match result (if any).
            pending_confirm: Whether we are waiting for Y/N confirmation.

        Returns:
            The composed frame (not yet shown — call show()).
        """
        display = frame.copy()

        # Resize webcam to fit the left portion of the canvas
        cam_w = self.width - 400 if match else self.width
        cam_h = self.height - 50  # leave room for status bar
        display = cv2.resize(display, (cam_w, cam_h))

        # Draw face bounding boxes
        if faces:
            for face in faces:
                x1, y1, x2, y2 = self._scale_bbox(face.bbox, frame.shape, cam_w, cam_h)
                color = COL_GREEN if match and pending_confirm else (COL_YELLOW if match else COL_RED)
                cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
                label = f"{face.score:.1%}"
                cv2.putText(display, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        # Build full canvas
        canvas = np.full((self.height, self.width, 3), 30, dtype=np.uint8)
        canvas[:cam_h, :cam_w] = display

        # Side panel with match info
        if match:
            self._draw_match_panel(canvas, match, pending_confirm, cam_w)

        # Controls help bar (above status bar)
        self._draw_controls_bar(canvas, pending_confirm)

        # Status bar at the bottom
        self._draw_status_bar(canvas)

        # Flash message overlay
        if self._flash_msg and time.time() < self._flash_until:
            self._draw_flash(canvas)
        elif time.time() >= self._flash_until:
            self._flash_msg = None

        return canvas

    def show(self, canvas: np.ndarray) -> int:
        """Display the canvas and wait for a key press (1 ms)."""
        cv2.imshow(self.WINDOW_NAME, canvas)
        return cv2.waitKey(1) & 0xFF

    # ------------------------------------------------------------------ #
    #  Drawing helpers                                                    #
    # ------------------------------------------------------------------ #

    def _scale_bbox(
        self, bbox: np.ndarray, orig_shape: tuple, target_w: int, target_h: int
    ) -> tuple[int, int, int, int]:
        oh, ow = orig_shape[:2]
        sx, sy = target_w / ow, target_h / oh
        x1, y1, x2, y2 = bbox
        return int(x1 * sx), int(y1 * sy), int(x2 * sx), int(y2 * sy)

    def _draw_match_panel(
        self, canvas: np.ndarray, match: MatchResult, pending: bool, x_offset: int
    ) -> None:
        panel_w = self.width - x_offset
        panel_h = self.height - 50
        # Panel background
        canvas[:panel_h, x_offset:] = np.array(COL_PANEL_BG, dtype=np.uint8)

        # Vertical divider
        cv2.line(canvas, (x_offset, 0), (x_offset, panel_h), COL_ACCENT, 2)

        y = 20
        pad = x_offset + 15

        # Header
        cv2.putText(canvas, "MATCH FOUND", (pad, y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, COL_GREEN, 2)
        y += 50

        # Participant photo
        photo_path = config.photos_path() / f"{match.participant_id}.jpg"
        if photo_path.exists():
            try:
                photo = cv2.imread(str(photo_path))
                if photo is not None:
                    ph = 150
                    pw = int(ph * photo.shape[1] / photo.shape[0])
                    pw = min(pw, panel_w - 30)
                    photo = cv2.resize(photo, (pw, ph))
                    canvas[y : y + ph, pad : pad + pw] = photo
                    y += ph + 15
            except Exception:
                y += 5

        # Name
        cv2.putText(canvas, match.name, (pad, y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.9, COL_WHITE, 2)
        y += 40

        # Institution
        if match.institution:
            cv2.putText(canvas, match.institution, (pad, y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, COL_WHITE, 1)
            y += 30

        # Category
        if match.category:
            cv2.putText(canvas, f"Category: {match.category}", (pad, y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, COL_ACCENT, 1)
            y += 30

        # Similarity
        sim_pct = f"Similarity: {match.similarity:.1%}"
        sim_col = COL_GREEN if match.similarity > 0.6 else COL_YELLOW
        cv2.putText(canvas, sim_pct, (pad, y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, sim_col, 1)
        y += 40

        # Confirmation prompt
        if pending:
            cv2.putText(canvas, "Confirm check-in?", (pad, y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, COL_YELLOW, 2)
            y += 35
            cv2.putText(canvas, "[Y] Yes   [N] No", (pad, y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.65, COL_WHITE, 1)

    def _draw_controls_bar(self, canvas: np.ndarray, pending: bool) -> None:
        bar_y = self.height - 50
        cv2.rectangle(canvas, (0, bar_y), (self.width, bar_y + 20), COL_DARK_BG, -1)
        controls = "[Q] Quit  [S] Sync  [M] Manual  [R] Toggle QR/Face  [C] Session"
        if pending:
            controls = "[Y] Confirm  [N] Reject  " + controls
        cv2.putText(canvas, controls, (10, bar_y + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.43, COL_WHITE, 1)

    def _draw_status_bar(self, canvas: np.ndarray) -> None:
        bar_y = self.height - 28
        cv2.rectangle(canvas, (0, bar_y), (self.width, self.height), COL_DARK_BG, -1)

        conn_label = "ONLINE" if self._connected else "OFFLINE"
        conn_col = COL_GREEN if self._connected else COL_RED
        status = (
            f"{conn_label}  |  Pending: {self._pending_sync_count}  |  "
            f"Mode: {self._mode}  |  Session: {self._session_name}  |  "
            f"Faces: {self._embeddings_count}  |  {self._status_msg}"
        )
        cv2.putText(canvas, status, (10, self.height - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.42, conn_col, 1)

    def _draw_flash(self, canvas: np.ndarray) -> None:
        overlay = canvas.copy()
        h, w = canvas.shape[:2]
        cv2.rectangle(overlay, (w // 4, h // 3), (3 * w // 4, h // 3 + 60), COL_BLACK, -1)
        canvas[:] = cv2.addWeighted(overlay, 0.7, canvas, 0.3, 0)
        cv2.putText(
            canvas,
            self._flash_msg,
            (w // 4 + 20, h // 3 + 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.85,
            self._flash_color,
            2,
        )


# ------------------------------------------------------------------ #
#  Standalone "no-match" frame helper                                 #
# ------------------------------------------------------------------ #

def draw_no_match_overlay(canvas: np.ndarray) -> None:
    """Draw a 'No match found' indicator on the frame."""
    h, w = canvas.shape[:2]
    cv2.putText(
        canvas,
        "No match found",
        (w // 2 - 120, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        COL_RED,
        2,
    )
