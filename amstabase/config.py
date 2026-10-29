"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from datetime import timedelta


class Config:
    """Default configuration for local and production deployments."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-change-me")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    LLM_REQUEST_TIMEOUT_SECONDS = float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "30"))
    RECIPE_SOURCE_MAX_CHARS = int(os.getenv("RECIPE_SOURCE_MAX_CHARS", "50000"))
    RECIPE_URL_MAX_BYTES = int(os.getenv("RECIPE_URL_MAX_BYTES", "1000000"))
    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=int(os.getenv("SESSION_LIFETIME_MINUTES", "30"))
    )
    SESSION_PERMANENT = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    AUTO_INIT_DB = True
