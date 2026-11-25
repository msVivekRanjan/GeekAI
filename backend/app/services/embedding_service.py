"""Face embedding service using InsightFace ArcFace model.

Produces 512-dimensional face embeddings. If the InsightFace model cannot be
loaded (missing weights, no GPU, etc.) the service falls back to a zero vector
and logs a warning — it never crashes the application.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

_model = None
_model_load_attempted = False


def _load_model():
    """Lazily load the InsightFace model once."""
    global _model, _model_load_attempted
    if _model_load_attempted:
        return _model
    _model_load_attempted = True
    try:
        import insightface
        from insightface.app import FaceAnalysis

        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640))
        _model = app
        logger.info("InsightFace model loaded successfully")
    except Exception:
        logger.warning("InsightFace model could not be loaded — embeddings will be zero vectors", exc_info=True)
        _model = None
    return _model


def generate_embedding(image_path: str) -> List[float]:
    """Generate a 512-d face embedding from an image file.

    Returns a zero vector if the model is unavailable or no face is detected.
    """
    model = _load_model()
    zero = [0.0] * 512

    if model is None:
        return zero

    try:
        import cv2

        img = cv2.imread(image_path)
        if img is None:
            logger.warning("Could not read image: %s", image_path)
            return zero

        faces = model.get(img)
        if not faces:
            logger.warning("No face detected in %s", image_path)
            return zero

        # Use the largest detected face
        face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        embedding: np.ndarray = face.embedding
        return embedding.tolist()
    except Exception:
        logger.exception("Error generating embedding for %s", image_path)
        return zero


def generate_embedding_from_bytes(image_bytes: bytes) -> List[float]:
    """Generate a 512-d face embedding directly from raw image bytes (for R2 / in-memory uploads)."""
    model = _load_model()
    zero = [0.0] * 512

    if model is None or not image_bytes:
        return zero

    try:
        import cv2

        arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            logger.warning("Could not decode image bytes for face embedding")
            return zero

        faces = model.get(img)
        if not faces:
            logger.warning("No face detected in uploaded image bytes")
            return zero

        face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        embedding: np.ndarray = face.embedding
        return embedding.tolist()
    except Exception:
        logger.exception("Error generating embedding from bytes")
        return zero
