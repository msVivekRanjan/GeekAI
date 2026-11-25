"""
Configuration module for Face Check-in application.
Loads settings from environment variables, .env file, or defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the face-checkin directory
_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path)


class Config:
    """Application configuration loaded from environment variables."""

    # Backend API
    API_URL: str = os.getenv("API_URL", "http://localhost:8000")

    # Event ID for which this volunteer app is running
    EVENT_ID: int = int(os.getenv("EVENT_ID", "1"))

    # Volunteer credentials for API authentication
    VOLUNTEER_EMAIL: str = os.getenv("VOLUNTEER_EMAIL", "volunteer@example.com")
    VOLUNTEER_PASSWORD: str = os.getenv("VOLUNTEER_PASSWORD", "password")

    # Camera settings
    CAMERA_INDEX: int = int(os.getenv("CAMERA_INDEX", "0"))

    # Face matching threshold (cosine similarity)
    MATCH_THRESHOLD: float = float(os.getenv("MATCH_THRESHOLD", "0.4"))

    # Embedding sync interval in seconds
    SYNC_INTERVAL: int = int(os.getenv("SYNC_INTERVAL", "300"))

    # Local cache directory (relative to face-checkin/)
    CACHE_DIR: str = os.getenv("CACHE_DIR", "cache")
    SQLITE_DB: str = os.getenv("SQLITE_DB", "offline.db")

    # InsightFace model name
    MODEL_NAME: str = os.getenv("MODEL_NAME", "buffalo_l")

    # UI window dimensions
    WINDOW_WIDTH: int = int(os.getenv("WINDOW_WIDTH", "1280"))
    WINDOW_HEIGHT: int = int(os.getenv("WINDOW_HEIGHT", "720"))

    # Retry settings for API calls
    API_RETRIES: int = int(os.getenv("API_RETRIES", "3"))
    API_TIMEOUT: int = int(os.getenv("API_TIMEOUT", "10"))

    @classmethod
    def cache_path(cls) -> Path:
        """Return the absolute path to the cache directory."""
        base = Path(__file__).parent
        path = base / cls.CACHE_DIR
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def photos_path(cls) -> Path:
        """Return the absolute path to the cached photos directory."""
        path = cls.cache_path() / "photos"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def embeddings_cache_file(cls) -> Path:
        """Return the path to the embeddings cache JSON file."""
        return cls.cache_path() / "embeddings_cache.json"

    @classmethod
    def sqlite_db_path(cls) -> Path:
        """Return the path to the local SQLite database file."""
        return cls.cache_path() / cls.SQLITE_DB


# Singleton instance
config = Config()
